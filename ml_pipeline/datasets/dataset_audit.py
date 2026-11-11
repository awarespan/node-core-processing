"""
AWARESPAN — Dataset Audit Utility
Forensic, read-only integrity audit of YOLO datasets, label balance, and image validity.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import glob
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from shared.config.settings import get_settings
from shared.logging.logger import get_logger

log = get_logger("ml_pipeline.dataset_audit")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".JPG", ".JPEG", ".PNG", ".BMP"}


def sha256(path: str) -> Optional[str]:
    """Compute SHA-256 of a file."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def audit_dataset_dir(dataset_path: str) -> Dict:
    """Audit images, labels, and classes in a YOLO dataset folder."""
    base = Path(dataset_path)
    if not base.exists():
        return {"exists": False, "path": str(dataset_path)}

    image_files = [f for f in base.rglob("*") if f.suffix in IMAGE_EXTS]
    label_files = [f for f in base.rglob("*.txt") if "label" in str(f).lower()]

    class_counts = {}
    for lbl in label_files:
        try:
            with open(lbl, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if parts:
                        cls_id = parts[0]
                        class_counts[cls_id] = class_counts.get(cls_id, 0) + 1
        except Exception:
            pass

    return {
        "exists": True,
        "path": str(base),
        "total_images": len(image_files),
        "total_labels": len(label_files),
        "class_distributions": class_counts,
    }


def main():
    settings = get_settings()
    data_dir = settings.dataset_dir
    log.info("Auditing dataset directory: %s", data_dir)
    res = audit_dataset_dir(data_dir)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
