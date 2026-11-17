"""Manifest-driven ensemble of specialist visual detectors for AWARESPAN."""

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import cv2

from shared.config.settings import get_settings
from shared.logging.logger import get_logger
from shared.models.events import Detection
from node_runtime.detection.visual.detector import VisualDetector

log = get_logger("node_runtime.visual_ensemble")


class VisualEnsembleDetector:
    """Run a small, sequential set of specialist detectors on each frame.

    Sequential execution intentionally bounds CPU and memory use on the Pi.
    Each specialist has a class allow-list so unrelated COCO classes cannot
    enter the threat-assessment policy.
    """

    def __init__(self, detectors: Sequence[VisualDetector]):
        self.detectors = list(detectors)
        if not self.detectors:
            raise ValueError("At least one visual detector is required")
        self.model_path = ";".join(detector.model_path for detector in self.detectors)
        self.model_ids = [getattr(detector, "model_id", Path(detector.model_path).stem) for detector in self.detectors]

    def infer(self, frame):
        all_detections: List[Detection] = []
        annotated = frame.copy()
        for detector in self.detectors:
            _, detections = detector.infer(frame)
            all_detections.extend(detections)

        for detection in all_detections:
            x1, y1, x2, y2 = detection.bbox
            label = f"{detection.label} {detection.confidence:.2f}"
            colour = (0, 165, 255) if detection.label.lower() in {"person", "dog"} else (0, 80, 255)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), colour, 2)
            cv2.putText(annotated, label, (x1, max(18, y1 - 7)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, colour, 2, cv2.LINE_AA)

        return annotated, all_detections

    def health_check(self) -> bool:
        return bool(self.detectors) and all(detector.model is not None for detector in self.detectors)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_visual_detector(
    manifest_path: Optional[Path] = None,
    profile: Optional[str] = None,
    imgsz: int = 640,
    confidence: Optional[float] = None,
) -> VisualEnsembleDetector:
    """Load the visual models declared for a deployment profile."""
    settings = get_settings()
    root = settings.repo_root
    path = manifest_path or Path(settings.ml_deployment_manifest)
    if not path.is_absolute():
        path = root / path
    selected_profile = profile or settings.ml_deployment_profile

    manifest = json.loads(path.read_text(encoding="utf-8"))
    profile_data = manifest.get("profiles", {}).get(selected_profile)
    if not isinstance(profile_data, dict):
        raise ValueError(f"Deployment profile '{selected_profile}' is missing from {path}")
    model_ids = profile_data.get("model_ids", [])
    if not model_ids:
        raise ValueError(f"Deployment profile '{selected_profile}' has no model_ids")

    entries: Dict[str, dict] = {entry.get("model_id"): entry for entry in manifest.get("active_models", [])}
    loaded: List[VisualDetector] = []
    for model_id in model_ids:
        entry = entries.get(model_id)
        if not entry or not entry.get("enabled", True):
            log.warning("Visual model %s is not enabled in deployment manifest", model_id)
            continue
        if entry.get("modality") != "visual":
            continue

        artifact = Path(entry.get("artifact_path", ""))
        if not artifact.is_absolute():
            artifact = root / artifact
        if not artifact.is_file():
            log.warning("Skipping %s: model artifact is unavailable at %s", model_id, artifact)
            continue

        expected = str(entry.get("sha256", "")).lower()
        if expected and len(expected) == 64:
            if _sha256(artifact).lower() != expected:
                log.error("Skipping %s: model checksum does not match deployment manifest", model_id)
                continue

        detector = VisualDetector(
            model_path=str(artifact),
            imgsz=int(entry.get("imgsz", imgsz)),
            confidence=float(entry.get("confidence_threshold", confidence or settings.confidence_threshold)),
            allowed_labels=set(entry.get("allowed_labels", [])),
        )
        detector.model_id = model_id
        if detector.model is None:
            log.warning("Skipping %s because its inference model did not load", model_id)
            continue
        loaded.append(detector)
        log.info("Loaded visual specialist %s (%s)", model_id, artifact.name)

    if not loaded:
        raise RuntimeError(f"No visual models from profile '{selected_profile}' could be loaded")

    log.info("Visual profile %s active with %d specialist model(s)", selected_profile, len(loaded))
    return VisualEnsembleDetector(loaded)
