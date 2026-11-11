"""
AWARESPAN — Direct Weapon Training
Direct fine-tuning for knife and gun detection.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import os
from ultralytics import YOLO

from shared.config.settings import get_settings


def train_weapon(data_yaml_path: str = "gun-and-knife-detection-1/data.yaml", epochs: int = 25):
    print("Loading base YOLOv8n model...")
    model = YOLO("yolov8n.pt")

    print(f"Starting direct weapon training ({epochs} epochs)...")
    model.train(
        data=data_yaml_path,
        epochs=epochs,
        batch=2,
        imgsz=320,
        device="cpu",
        save_period=10,
        project="runs/detect",
        name="train_weapon",
        exist_ok=True,
    )
    print("Training finished!")


if __name__ == "__main__":
    train_weapon()
