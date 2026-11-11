"""
AWARESPAN — Model Packager & Release Artifact Generator
Packages trained YOLO weights into versioned production artifacts with SHA256 integrity and metadata.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from shared.config.settings import get_settings
from shared.logging.logger import get_logger
from shared.models.events import ModelMetadata

log = get_logger("ml_pipeline.model_packager")


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 checksum of model weights."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class ModelPackager:
    """Packages and validates production model artifacts."""

    def __init__(self):
        self.settings = get_settings()

    def package_model(
        self,
        weights_path: str,
        model_name: str = "yolov8n_best_weapon",
        version: str = "1.0.0",
        classes: Optional[List[str]] = None,
        confidence_threshold: float = 0.45,
        target_dir: Optional[str] = None,
    ) -> Optional[Path]:
        """
        Package weights file into versioned deployment artifact with metadata.
        """
        src = Path(weights_path)
        if not src.is_file():
            log.error("Model weights file not found: %s", weights_path)
            return None

        # Inspect model classes if possible
        model_classes = classes or ["knife", "gun"]
        try:
            from ultralytics import YOLO
            m = YOLO(str(src))
            names = getattr(m, "names", {})
            if names and isinstance(names, dict):
                model_classes = [names[k] for k in sorted(names.keys())]
        except Exception as exc:
            log.warning("Could not dynamically inspect model classes: %s", exc)

        dest_dir = Path(target_dir) if target_dir else self.settings.repo_root / "shared" / "models"
        dest_dir.mkdir(parents=True, exist_ok=True)

        target_weights = dest_dir / f"{model_name}.pt"
        log.info("Copying weights to %s...", target_weights)
        shutil.copy2(src, target_weights)

        checksum = compute_sha256(target_weights)
        metadata = ModelMetadata(
            model_name=model_name,
            version=version,
            classes=model_classes,
            num_classes=len(model_classes),
            input_resolution=[640, 640],
            confidence_threshold=confidence_threshold,
            sha256=checksum,
            created_at=datetime.now(timezone.utc).isoformat(),
            target_hardware="Raspberry Pi 5",
        )

        metadata_path = dest_dir / f"{model_name}_metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata.to_dict(), f, indent=2)

        log.info("Model packaged successfully at %s (SHA256: %s)", target_weights, checksum[:16])
        return target_weights


def main():
    parser = argparse.ArgumentParser(description="Package production model artifact")
    parser.add_argument("--weights", required=True, help="Path to input weights .pt")
    parser.add_argument("--name", default="yolov8n_best_weapon", help="Artifact model name")
    parser.add_argument("--version", default="1.0.0", help="Model semantic version")
    parser.add_argument("--conf", type=float, default=0.45, help="Recommended confidence threshold")
    parser.add_argument("--out", default=None, help="Target packaging output directory")
    args = parser.parse_args()

    packager = ModelPackager()
    res = packager.package_model(
        weights_path=args.weights,
        model_name=args.name,
        version=args.version,
        confidence_threshold=args.conf,
        target_dir=args.out,
    )
    if not res:
        exit(1)


if __name__ == "__main__":
    main()
