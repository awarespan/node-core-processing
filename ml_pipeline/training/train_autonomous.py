"""
AWARESPAN — Autonomous Model Training Orchestrator
Module 3: Autonomous YOLOv8 training loop with checkpoint preservation, safe resume, and thermal protection.

DISABLED BY DEFAULT ON PRODUCTION NODES (ML_TRAINING_ENABLED=false).
Model training runs separately on training machines or explicitly enabled environments.

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
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import yaml

from shared.config.settings import get_settings
from shared.logging.logger import get_logger
from shared.utilities.system import get_throttled_state
from node_runtime.monitoring.telegram_notify import send_message

log = get_logger("ml_pipeline.train_autonomous")


def resolve_dataset(settings) -> Optional[str]:
    """Find valid dataset yaml."""
    candidates = [
        Path(settings.dataset_dir) / "data.yaml",
        settings.repo_root / "datasets" / "data.yaml",
        Path.home() / "edge-ai" / "unified_weapon_dataset" / "data.yaml",
        Path.home() / "gun-and-knife-detection-1" / "data.yaml",
    ]
    for c in candidates:
        if c.is_file():
            return str(c.resolve())
    return None


def train(epochs: int = 100, batch: int = 4, imgsz: int = 416, force: bool = False, dry_run: bool = False) -> None:
    settings = get_settings()

    # 1. Enforce ML training toggle
    if not settings.ml_training_enabled and not force:
        msg = (
            "⚠️ ML Training is DISABLED by default on this production node (ML_TRAINING_ENABLED=false).\n"
            "Production nodes run inference and deterrence only.\n"
            "To train, run on a dedicated training workstation or pass '--force' / set ML_TRAINING_ENABLED=true."
        )
        log.warning(msg)
        print(msg)
        return

    # 2. Hardware Thermal & Undervoltage Safety Check
    power = get_throttled_state()
    if power.undervoltage_now and not force:
        err = f"ABORT: Active undervoltage detected ({power.throttled_raw}). Training would crash the Pi."
        log.error(err)
        print(err)
        send_message(f"❌ <b>AWARESPAN Training Aborted</b>\nReason: Undervoltage detected.")
        sys.exit(1)

    if power.temp_c and power.temp_c > 78.0 and not force:
        err = f"ABORT: CPU temperature too high ({power.temp_c:.1f}°C). Cooling down required."
        log.error(err)
        print(err)
        sys.exit(1)

    # 3. Resolve Dataset
    data_yaml = resolve_dataset(settings)
    if not data_yaml:
        err = "No valid data.yaml found for training."
        log.error(err)
        print(err)
        sys.exit(1)

    log.info("Starting training with dataset: %s", data_yaml)
    if dry_run:
        print(f"[dry-run] Validation succeeded. Dataset: {data_yaml}")
        return

    try:
        from ultralytics import YOLO
    except ImportError:
        err = "Ultralytics package is not installed."
        log.error(err)
        print(err)
        sys.exit(1)

    checkpoint_dir = Path(settings.checkpoint_dir) / "detect" / "train" / "weights"
    last_pt = checkpoint_dir / "last.pt"
    can_resume = last_pt.exists()

    run_name = "train" if can_resume else f"train_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    if can_resume:
        log.info("Resuming training from checkpoint: %s", last_pt)
        model = YOLO(str(last_pt))
    else:
        log.info("Starting fresh training run from yolov8n.pt...")
        model = YOLO("yolov8n.pt")

    send_message(f"🚀 <b>AWARESPAN Training Started</b>\nRun: <code>{run_name}</code>\nEpochs: {epochs}")

    try:
        model.train(
            data=data_yaml,
            epochs=epochs,
            batch=batch,
            imgsz=imgsz,
            device="cpu",
            workers=0,
            save_period=5,
            project=str(Path(settings.checkpoint_dir) / "detect"),
            name=run_name,
            exist_ok=can_resume,
            resume=can_resume,
            plots=True,
            verbose=True,
        )
        log.info("Training run %s completed successfully!", run_name)
        send_message(f"✅ <b>AWARESPAN Training Complete</b>\nRun: <code>{run_name}</code>")

    except (RuntimeError, MemoryError, OSError) as exc:
        if "out of memory" in str(exc).lower() or isinstance(exc, (MemoryError, OSError)):
            log.warning("Memory pressure encountered; falling back to batch=2, imgsz=320...")
            fallback_run = f"train_fallback_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            model_fb = YOLO("yolov8n.pt")
            model_fb.train(
                data=data_yaml,
                epochs=epochs,
                batch=2,
                imgsz=320,
                device="cpu",
                workers=0,
                save_period=5,
                project=str(Path(settings.checkpoint_dir) / "detect"),
                name=fallback_run,
                plots=True,
            )
            send_message(f"✅ <b>AWARESPAN Fallback Training Complete</b>\nRun: <code>{fallback_run}</code>")
        else:
            raise


def main():
    parser = argparse.ArgumentParser(description="AWARESPAN Model Training Orchestrator")
    parser.add_argument("--epochs", type=int, default=100, help="Number of training epochs")
    parser.add_argument("--batch", type=int, default=4, help="Batch size")
    parser.add_argument("--imgsz", type=int, default=416, help="Image resolution")
    parser.add_argument("--force", action="store_true", help="Force training even if ML_TRAINING_ENABLED=false")
    parser.add_argument("--dry-run", action="store_true", help="Test configuration without training")
    args = parser.parse_args()

    train(epochs=args.epochs, batch=args.batch, imgsz=args.imgsz, force=args.force, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
