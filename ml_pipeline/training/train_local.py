"""
AWARESPAN — Local Prototype Training Script
Run quick prototype training runs on workstation CPU/GPU.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import os
from ultralytics import YOLO, settings


def main():
    dataset_dir = os.path.abspath(os.path.join(os.getcwd(), "datasets"))
    os.makedirs(dataset_dir, exist_ok=True)
    settings.update({"datasets_dir": dataset_dir})

    print("Starting YOLOv8 prototype training...")
    model = YOLO("yolov8n.pt")

    try:
        model.train(
            data="coco128.yaml",
            epochs=50,
            imgsz=640,
            batch=4,
            device="cpu",
            project="ml_pipeline/runs",
            name="threat_prototype",
        )
        print("Training completed.")
    except Exception as exc:
        print(f"Training failed: {exc}")


if __name__ == "__main__":
    main()
