#!/usr/bin/env python3
"""
Autonomous weapon detection training script for Raspberry Pi 5.
Designed to run safely as a background process or systemd service.
Features:
- Dynamic class configuration matching data.yaml (prevents false incompatibility)
- Checkpoint preservation (never overwrites previous run weights)
- Timestamped run directories for new runs
- Safe graceful fallback on memory constraints
- Telegram notifications
"""

import argparse
from datetime import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback

import yaml

HOME = os.path.expanduser("~")
VENV_PYTHON = os.path.join(HOME, "edge-ai", "pi", ".venv", "bin", "python3")
UNIFIED_DATASET = os.path.join(HOME, "edge-ai", "unified_weapon_dataset", "data.yaml")
FALLBACK_DATASET = os.path.join(HOME, "gun-and-knife-detection-1", "data.yaml")
CHECKPOINT = os.path.join(HOME, "runs", "detect", "train", "weights", "last.pt")
NOTIFY_SCRIPT = os.path.join(HOME, "edge-ai", "telegram_notify.py")
MANIFEST_PATHS = [
    os.path.join(HOME, "edge-ai", "dataset_registry.json"),
    os.path.join(HOME, "edge-ai", "datasets_manifest.json"),
]

# Add edge-ai to path for telegram_notify
sys.path.insert(0, os.path.join(HOME, "edge-ai"))


def notify(cmd, *args):
    """Send a Telegram notification if configured."""
    try:
        if os.path.exists(NOTIFY_SCRIPT) and os.path.exists(VENV_PYTHON):
            subprocess.run(
                [VENV_PYTHON, NOTIFY_SCRIPT, cmd] + list(args),
                timeout=30, check=False,
                cwd=HOME
            )
    except Exception:
        pass


def load_manifest():
    """Load dataset manifest or registry from known locations."""
    for path in MANIFEST_PATHS:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return json.load(f), path
            except Exception:
                continue
    return None, None


def load_data_yaml(path):
    """Load and return data.yaml content or None."""
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def get_dataset_classes(data_yaml_path):
    """Dynamically determine classes from data.yaml, falling back to gun & knife."""
    data = load_data_yaml(data_yaml_path)
    if data and "names" in data:
        names = data["names"]
        if isinstance(names, dict):
            names = [names[k] for k in sorted(names.keys())]
        return names, len(names)
    return ["gun", "knife"], 2


def backup_existing_weights():
    """Safely back up any existing checkpoints into an archive directory."""
    weights_dir = os.path.join(HOME, "runs", "detect", "train", "weights")
    if not os.path.exists(weights_dir):
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir = os.path.join(HOME, "runs", "detect", "checkpoints_archive", timestamp)
    os.makedirs(archive_dir, exist_ok=True)

    copied = 0
    for fname in os.listdir(weights_dir):
        if fname.endswith(".pt"):
            src = os.path.join(weights_dir, fname)
            dst = os.path.join(archive_dir, fname)
            shutil.copy2(src, dst)
            copied += 1

    if copied > 0:
        print(f"[safety] Archived {copied} checkpoints to {archive_dir}")


def verify_checkpoint_compatibility(checkpoint_path, expected_nc, expected_classes):
    """
    Verify that a YOLO checkpoint is compatible with the expected dataset.
    Returns (True, reason) if compatible, (False, reason) if not.
    """
    if not os.path.exists(checkpoint_path):
        return False, "No checkpoint found"

    try:
        from ultralytics import YOLO
        model = YOLO(checkpoint_path)
        ckpt_data = getattr(model, "ckpt", None)
        if not ckpt_data or not isinstance(ckpt_data, dict):
            return True, "Checkpoint loaded, metadata not directly inspectable"

        nc = ckpt_data.get("nc", None)
        if nc is not None and nc != expected_nc:
            return False, f"Checkpoint has nc={nc}, but dataset requires nc={expected_nc}"

        names = ckpt_data.get("names", {})
        if names and isinstance(names, dict) and len(names) == expected_nc:
            names_list = [names[i] for i in range(len(names))]
            if names_list != expected_classes:
                return False, f"Checkpoint class names {names_list} mismatch {expected_classes}"

        return True, f"Checkpoint compatible: nc={nc}"
    except Exception as e:
        return True, f"Could not inspect checkpoint metadata ({e}), allowing resume attempt"


def resolve_dataset():
    """Identify the valid dataset yaml path."""
    if os.path.exists(UNIFIED_DATASET):
        return UNIFIED_DATASET
    elif os.path.exists(FALLBACK_DATASET):
        print(f"Using fallback dataset: {FALLBACK_DATASET}")
        return FALLBACK_DATASET
    else:
        raise FileNotFoundError(f"Neither {UNIFIED_DATASET} nor {FALLBACK_DATASET} exists.")


def train(epochs=150, batch=4, imgsz=416, dry_run=False):
    """Execute training safely without overwriting previous runs."""
    from ultralytics import YOLO

    data_yaml = resolve_dataset()
    expected_classes, expected_nc = get_dataset_classes(data_yaml)
    print(f"[config] Dataset: {data_yaml}")
    print(f"[config] Expected classes: {expected_classes} (nc={expected_nc})")

    # Check manifest
    manifest, manifest_path = load_manifest()
    if manifest:
        print(f"[config] Found manifest at: {manifest_path}")

    # Check resume eligibility
    can_resume = False
    if os.path.exists(CHECKPOINT):
        compat, reason = verify_checkpoint_compatibility(CHECKPOINT, expected_nc, expected_classes)
        print(f"[checkpoint] Compatibility: {reason}")
        can_resume = compat

    # Archive existing weights before starting anything
    backup_existing_weights()

    if dry_run:
        print("[dry-run] Dry run completed successfully. Configuration is valid.")
        return

    run_name = "train" if can_resume else f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    resume_flag = can_resume

    if can_resume:
        print(f"Resuming run from {CHECKPOINT} in runs/detect/train")
        model = YOLO(CHECKPOINT)
    else:
        print(f"Starting new isolated run: runs/detect/{run_name}")
        model = YOLO("yolov8n.pt")

    notify("start", f"Run: {run_name}\nClasses: {expected_classes}\nResume: {resume_flag}")

    try:
        model.train(
            data=data_yaml,
            epochs=epochs,
            batch=batch,
            imgsz=imgsz,
            device="cpu",
            workers=0,
            save_period=5,
            project="runs/detect",
            name=run_name,
            exist_ok=can_resume,
            resume=resume_flag,
            patience=0,
            cache=False,
            plots=True,
            verbose=True,
        )
        notify("complete", f"Training {run_name} complete!")
        print(f"Training run {run_name} complete!")

    except (RuntimeError, MemoryError, OSError) as e:
        if "out of memory" in str(e).lower() or isinstance(e, (MemoryError, OSError)):
            print("[fallback] Memory limit encountered, falling back to batch=2, imgsz=320...")
            notify("crash", f"OOM fallback triggered: {str(e)[:200]}")
            fallback_run = f"train_fallback_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            model_fallback = YOLO("yolov8n.pt")
            model_fallback.train(
                data=data_yaml,
                epochs=epochs,
                batch=2,
                imgsz=320,
                device="cpu",
                workers=0,
                save_period=5,
                project="runs/detect",
                name=fallback_run,
                exist_ok=False,
                resume=False,
                patience=0,
                cache=False,
                plots=True,
                verbose=True,
            )
            notify("complete", f"Fallback training {fallback_run} complete!")
        else:
            raise


def main():
    parser = argparse.ArgumentParser(description="Autonomous Safe YOLOv8 Training")
    parser.add_argument("--epochs", type=int, default=150, help="Number of epochs")
    parser.add_argument("--batch", type=int, default=4, help="Batch size")
    parser.add_argument("--imgsz", type=int, default=416, help="Image size")
    parser.add_argument("--dry-run", action="store_true", help="Validate config without training")
    args = parser.parse_args()

    try:
        train(epochs=args.epochs, batch=args.batch, imgsz=args.imgsz, dry_run=args.dry_run)
    except Exception as e:
        tb = traceback.format_exc()
        print(f"FATAL: {e}\n{tb}", file=sys.stderr)
        notify("crash", tb[:500])
        sys.exit(1)


if __name__ == "__main__":
    main()
