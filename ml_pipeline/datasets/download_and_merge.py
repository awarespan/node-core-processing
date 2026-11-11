"""
AWARESPAN — Dataset Downloader & Merger
Downloads weapon detection datasets and merges them into a unified YOLO dataset with deduplication.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import glob
import hashlib
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Set

import yaml

from shared.config.settings import get_settings
from shared.logging.logger import get_logger

log = get_logger("ml_pipeline.download_and_merge")

CLASSES = ["gun", "knife"]
SEEN_IMAGE_HASHES: Set[str] = set()


def get_file_sha256(filepath: str) -> str:
    """Compute SHA-256 hash of an image file for deduplication."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def assign_split_deterministically(img_sha256: str) -> str:
    """Deterministically assign an image to train/valid/test based on content hash."""
    bucket = int(img_sha256[:8], 16) % 100
    if bucket < 80:
        return "train"
    elif bucket < 90:
        return "valid"
    else:
        return "test"


def check_disk_space(path: str) -> float:
    """Return free space in GB."""
    try:
        stat = os.statvfs(path)
        return (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
    except Exception:
        return 50.0


def merge_datasets(source_dirs: List[str], output_dir: str):
    """Merge YOLO-formatted dataset directories into unified dataset."""
    log.info("Merging %d datasets into %s...", len(source_dirs), output_dir)
    out_path = Path(output_dir)

    for split in ("train", "valid", "test"):
        (out_path / "images" / split).mkdir(parents=True, exist_ok=True)
        (out_path / "labels" / split).mkdir(parents=True, exist_ok=True)

    # Write data.yaml
    data_yaml = {
        "path": str(out_path.resolve()),
        "train": "images/train",
        "val": "images/valid",
        "test": "images/test",
        "nc": len(CLASSES),
        "names": CLASSES,
    }
    with open(out_path / "data.yaml", "w", encoding="utf-8") as f:
        yaml.dump(data_yaml, f)

    log.info("data.yaml created at %s", out_path / "data.yaml")
