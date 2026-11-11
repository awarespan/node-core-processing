#!/usr/bin/env python3
"""
Forensic audit of existing datasets on the Raspberry Pi.
Read-only integrity audit — does NOT modify any dataset files.
Produces a machine-readable audit report and a human-readable summary.
"""

import os
import sys
import json
import hashlib
import subprocess
import glob as glob_mod
from datetime import datetime
from pathlib import Path

HOME = os.path.expanduser("~")
REPORT_DIR = os.path.join(HOME, "edge-ai", "audit_reports")
os.makedirs(REPORT_DIR, exist_ok=True)

# ── Config ────────────────────────────────────────────────────────────────────

DATASET_DIRS = [
    os.path.join(HOME, "edge-ai", "unified_weapon_dataset"),
    os.path.join(HOME, "edge-ai", "weapon_datasets"),
    os.path.join(HOME, "gun-and-knife-detection-1"),
]

CHECKPOINT_DIRS = [
    os.path.join(HOME, "runs", "detect", "train", "weights"),
    os.path.join(HOME, "runs", "detect", "train"),
]

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".JPG", ".JPEG", ".PNG", ".BMP"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg):
    print(f"[audit] {msg}", flush=True)


def sha256(path):
    """Compute SHA-256 of a file."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def check_image(path):
    """Validate image is readable. Returns (ok, dims, error)."""
    try:
        from PIL import Image
        with Image.open(path) as img:
            dims = img.size
        return True, dims, None
    except Exception as e:
        return False, None, str(e)[:100]


def parse_yolo_label(path):
    """
    Parse YOLO label file. Returns list of (class_id, x, y, w, h) or None if malformed.
    class_id must be int, coordinates must be finite floats in [0, 1] (centers) and
    positive (widths/heights), and boxes must fit within [0, 1].
    """
    lines = []
    try:
        with open(path, "r") as f:
            content = f.read()
        if not content.strip():
            return []  # Empty = intentional negative example

        for lineno, line in enumerate(content.strip().split("\n"), 1):
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 5:
                return None  # Malformed

            try:
                cls = int(parts[0])
                x = float(parts[1])
                y = float(parts[2])
                w = float(parts[3])
                h = float(parts[4])
            except (ValueError, IndexError):
                return None

            # Validate finite and range
            for val in [x, y, w, h]:
                if not (-1e9 < val < 1e9):
                    return None

            # Centers must be in [0, 1]
            if not (0 <= x <= 1 and 0 <= y <= 1):
                return None
            # Widths/heights must be positive and fit in [0, 1]
            if not (0 < w <= 1 and 0 < h <= 1):
                return None
            # Box must fit within image
            if x - w / 2 < -1e-6 or y - h / 2 < -1e-6 or x + w / 2 > 1 + 1e-6 or y + h / 2 > 1 + 1e-6:
                return None

            lines.append((cls, x, y, w, h))
        return lines
    except Exception:
        return None


def find_images_and_labels(root_dir):
    """Find all image/label pairs recursively."""
    pairs = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for f in filenames:
            ext = os.path.splitext(f)[1]
            if ext not in IMAGE_EXTS:
                continue
            img_path = os.path.join(dirpath, f)
            base = os.path.splitext(f)[0]
            # Try same dir
            lbl_path = os.path.join(dirpath, base + ".txt")
            # Try replacing images/labels
            if not os.path.exists(lbl_path):
                lbl_path = os.path.join(
                    dirpath.replace("/images", "/labels").replace("\\images", "\\labels"),
                    base + ".txt"
                )
            pairs.append((img_path, lbl_path if os.path.exists(lbl_path) else None))
    return pairs


def inventory_dir(path):
    """Return inventory dict for a directory."""
    if not os.path.exists(path):
        return None

    total_size = 0
    file_count = 0
    subdirs = []
    for dirpath, dirs, files in os.walk(path):
        for f in files:
            fp = os.path.join(dirpath, f)
            try:
                total_size += os.path.getsize(fp)
            except OSError:
                pass
            file_count += 1
        for d in dirs:
            subdirs.append(os.path.join(dirpath, d))

    return {
        "path": path,
        "exists": True,
        "total_size_bytes": total_size,
        "total_files": file_count,
        "subdirs": len(subdirs),
        "mtime": datetime.fromtimestamp(os.path.getmtime(path)).isoformat(),
    }


def inventory_checkpoints(path):
    """Inventory checkpoint files."""
    if not os.path.exists(path):
        return []
    results = []
    for f in os.listdir(path):
        fp = os.path.join(path, f)
        if os.path.isfile(fp):
            results.append({
                "name": f,
                "path": fp,
                "size_bytes": os.path.getsize(fp),
                "sha256": sha256(fp),
                "mtime": datetime.fromtimestamp(os.path.getmtime(fp)).isoformat(),
            })
    return results


# ── Main audit ────────────────────────────────────────────────────────────────

def run_audit():
    log("Starting forensic dataset audit...")
    audit_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(REPORT_DIR, f"audit_{audit_id}.json")
    summary_path = os.path.join(REPORT_DIR, f"audit_{audit_id}_summary.txt")

    report = {
        "audit_id": audit_id,
        "timestamp": datetime.now().isoformat(),
        "hostname": subprocess.run(["hostname"], capture_output=True, text=True).stdout.strip(),
        "unified_dataset_dir": os.path.join(HOME, "edge-ai", "unified_weapon_dataset"),
        "datasets": {},
        "checkpoints": [],
        "global_stats": {},
    }

    all_samples = {"total": 0, "valid": 0, "malformed_label": 0, "missing_label": 0,
                   "invalid_class": 0, "bad_image": 0, "duplicate_images": 0,
                   "empty_label": 0, "unknown": 0}

    # ── 1. Inventory dataset directories ──────────────────────────────────────
    for dset_path in DATASET_DIRS:
        name = os.path.basename(dset_path)
        log(f"Inventorying {name}...")
        inv = inventory_dir(dset_path)
        if inv:
            report["datasets"][name] = inv

        # Audit samples in unified dataset splits
        if "unified" in name or os.path.exists(os.path.join(dset_path, "train")):
            for split in ["train", "valid", "val", "test"]:
                img_dir = os.path.join(dset_path, split, "images")
                if not os.path.exists(img_dir):
                    continue

                log(f"  Auditing {name}/{split}...")
                pairs = find_images_and_labels(img_dir)

                split_stats = {
                    "total_samples": len(pairs),
                    "valid": 0, "malformed_label": 0, "missing_label": 0,
                    "invalid_class": 0, "bad_image": 0, "empty_label": 0,
                    "samples": [],
                }

                # Check for exact duplicate images
                seen_hashes = {}
                dupes = set()

                for img_path, lbl_path in pairs:
                    sample = {
                        "img": img_path,
                        "lbl": lbl_path,
                        "status": "UNKNOWN",
                        "reason": None,
                    }

                    # Image check
                    img_ok, dims, img_err = check_image(img_path)
                    if not img_ok:
                        sample["status"] = "BAD_IMAGE"
                        sample["reason"] = img_err
                        all_samples["bad_image"] += 1
                    else:
                        sample["img_dims"] = dims
                        sample["img_sha256"] = sha256(img_path)

                        # Check for duplicates
                        img_hash = sample["img_sha256"]
                        if img_hash in seen_hashes:
                            dupes.add(img_hash)
                            sample["status"] = "DUPLICATE"
                            sample["reason"] = f"Duplicate of {seen_hashes[img_hash]}"
                            all_samples["duplicate_images"] += 1
                        else:
                            seen_hashes[img_hash] = img_path

                    # Label check
                    if lbl_path is None or not os.path.exists(lbl_path):
                        sample["status"] = "MISSING_LABEL"
                        all_samples["missing_label"] += 1
                    else:
                        parsed = parse_yolo_label(lbl_path)
                        if parsed is None:
                            sample["status"] = "MALFORMED_LABEL"
                            all_samples["malformed_label"] += 1
                        elif len(parsed) == 0:
                            sample["status"] = "EMPTY_LABEL"
                            sample["reason"] = "Intentional negative example (empty label file)"
                            all_samples["empty_label"] += 1
                            all_samples["valid"] += 1
                        else:
                            # Check class IDs — for unified dataset, valid range is 0-2
                            max_cls = max(p[0] for p in parsed)
                            if max_cls > 2:  # Only gun(0), knife(1), dangerous_animal(2) are valid
                                sample["status"] = "INVALID_CLASS"
                                sample["reason"] = f"Class ID {max_cls} > 2 (max valid class)"
                                all_samples["invalid_class"] += 1
                            else:
                                sample["status"] = "VALID"
                                sample["annotations"] = len(parsed)
                                all_samples["valid"] += 1

                    split_stats["samples"].append(sample)
                    all_samples["total"] += 1
                    split_stats[sample["status"].lower().replace(" ", "_")] = \
                        split_stats.get(sample["status"].lower().replace(" ", "_"), 0) + 1

                if name not in report["datasets"]:
                    report["datasets"][name] = {"path": dset_path}
                if "splits" not in report["datasets"][name]:
                    report["datasets"][name]["splits"] = {}
                report["datasets"][name]["splits"][split] = {
                    "total": split_stats["total_samples"],
                    "valid": split_stats["valid"],
                    "malformed_label": split_stats["malformed_label"],
                    "missing_label": split_stats["missing_label"],
                    "invalid_class": split_stats["invalid_class"],
                    "bad_image": split_stats["bad_image"],
                    "empty_label": split_stats["empty_label"],
                    "duplicate_images": sum(1 for s in split_stats["samples"] if s["status"] == "DUPLICATE"),
                }

    # ── 2. Inventory checkpoints ──────────────────────────────────────────────
    log("Inventorying checkpoints...")
    all_checkpoints = []
    for cp_dir in CHECKPOINT_DIRS:
        cps = inventory_checkpoints(cp_dir)
        all_checkpoints.extend(cps)

    report["checkpoints"] = all_checkpoints
    report["global_stats"] = all_samples

    # ── 3. Write reports ──────────────────────────────────────────────────────
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    log(f"Machine-readable report: {report_path}")

    # ── 4. Human-readable summary ─────────────────────────────────────────────
    total = all_samples["total"]
    valid = all_samples["valid"]
    with open(summary_path, "w") as f:
        f.write(f"SIP Dataset Forensic Audit\n")
        f.write(f"Audit ID: {audit_id}\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Host: {report['hostname']}\n")
        f.write("=" * 60 + "\n\n")

        f.write(f"SUMMARY\n")
        f.write(f"  Total samples found: {total}\n")
        f.write(f"  Valid: {valid} ({100*valid/total:.1f}%)\n")
        f.write(f"  Malformed labels: {all_samples['malformed_label']}\n")
        f.write(f"  Missing labels: {all_samples['missing_label']}\n")
        f.write(f"  Invalid class IDs: {all_samples['invalid_class']}\n")
        f.write(f"  Bad images: {all_samples['bad_image']}\n")
        f.write(f"  Empty labels (negatives): {all_samples['empty_label']}\n")
        f.write(f"  Duplicate images: {all_samples['duplicate_images']}\n")
        f.write("\n")

        f.write(f"CLASS VALIDITY NOTE\n")
        f.write(f"  Valid class IDs: 0=gun, 1=knife, 2=dangerous_animal\n")
        f.write(f"  Samples with class ID > 2 are INVALID and indicate possible\n")
        f.write(f"  script-induced class mapping errors.\n")
        f.write("\n")

        f.write(f"CHECKPOINTS\n")
        for cp in all_checkpoints:
            f.write(f"  {cp['name']}: {cp['size_bytes']/1024/1024:.1f}MB, sha256={cp['sha256'][:16]}...\n")
        f.write("\n")

        f.write(f"PER-SPLIT BREAKDOWN\n")
        for dset_name, dset in report["datasets"].items():
            f.write(f"  {dset_name}:\n")
            if "splits" in dset:
                for split, stats in dset["splits"].items():
                    f.write(f"    {split}: {stats['total']} total, {stats['valid']} valid, "
                            f"{stats['invalid_class']} invalid-class, "
                            f"{stats['malformed_label']} malformed, "
                            f"{stats['missing_label']} missing\n")
        f.write("\n")

        f.write(f"ACTION REQUIRED\n")
        if all_samples["invalid_class"] > 0:
            f.write(f"  - {all_samples['invalid_class']} samples have invalid class IDs (>2)\n")
            f.write(f"    These may be from stale Kaggle datasets with wrong class mappings.\n")
            f.write(f"    See full report for paths and quarantine them.\n")
        if all_samples["duplicate_images"] > 0:
            f.write(f"  - {all_samples['duplicate_images']} duplicate images found.\n")
            f.write(f"    Split leakage possible.\n")
        if all_samples["malformed_label"] > 0:
            f.write(f"  - {all_samples['malformed_label']} malformed label files.\n")
        if all_samples["invalid_class"] == 0 and all_samples["duplicate_images"] == 0:
            f.write(f"  - No critical issues found.\n")

    log(f"Human-readable summary: {summary_path}")

    # Print summary
    print(f"\n{'='*60}")
    print(f"AUDIT COMPLETE — {audit_id}")
    print(f"{'='*60}")
    print(f"Total samples: {total} | Valid: {valid} ({100*valid/max(total,1):.1f}%)")
    print(f"Malformed: {all_samples['malformed_label']} | Missing: {all_samples['missing_label']}")
    print(f"Invalid class: {all_samples['invalid_class']} | Bad images: {all_samples['bad_image']}")
    print(f"Duplicates: {all_samples['duplicate_images']} | Empty (neg): {all_samples['empty_label']}")
    print(f"Checkpoints: {len(all_checkpoints)}")
    print(f"Full report: {report_path}")
    print(f"Summary: {summary_path}")

    return report


if __name__ == "__main__":
    run_audit()