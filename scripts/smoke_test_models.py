#!/usr/bin/env python3
"""Load each active Pi visual model and run CPU inference on committed sample images.

This is a model-load/inference smoke test, not an accuracy benchmark. Accuracy
requires a labelled, representative holdout set and is evaluated separately.
"""
import json
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "models/deployed/manifest.json"


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    profile = manifest["profiles"]["pi5_edge"]
    entries = {entry["model_id"]: entry for entry in manifest["active_models"]}
    samples = sorted((ROOT / "Samples/weapon_samples").glob("*.jpg"))[:3]
    if not samples:
        raise SystemExit("No committed model smoke-test images found")

    for model_id in profile["model_ids"]:
        entry = entries[model_id]
        artifact = ROOT / entry["artifact_path"]
        if not artifact.is_file():
            raise SystemExit(f"Missing model artifact: {artifact}")
        model = YOLO(str(artifact))
        names = model.names
        labels = set(names.values()) if isinstance(names, dict) else set(names)
        expected = set(entry["allowed_labels"])
        if not expected.issubset({str(label).lower() for label in labels}):
            raise SystemExit(f"{model_id}: model classes {labels} do not include {expected}")
        total = 0
        for sample in samples:
            results = model.predict(
                source=str(sample), imgsz=int(entry.get("imgsz", 640)),
                conf=0.10, device="cpu", verbose=False,
            )
            if not results or results[0].boxes is None:
                raise SystemExit(f"{model_id}: inference returned no result for {sample.name}")
            for box in results[0].boxes:
                confidence = float(box.conf[0].item())
                class_id = int(box.cls[0].item())
                if not 0.0 <= confidence <= 1.0 or class_id not in names:
                    raise SystemExit(f"{model_id}: invalid prediction for {sample.name}")
            total += len(results[0].boxes)
        print(f"PASS {model_id}: loaded {artifact.name}; classes={sorted(expected)}; "
              f"inferred {len(samples)} images; detections={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
