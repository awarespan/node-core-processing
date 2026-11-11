"""
AWARESPAN — Visual Detector
YOLOv8-based inference engine with confidence filtering, bbox extraction, and model loading.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import os
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from shared.config.settings import get_settings
from shared.logging.logger import get_logger
from shared.models.events import Detection

log = get_logger("node_runtime.visual_detector")

# Defensive lazy import for YOLO
try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None


class VisualDetector:
    """Wrapper around YOLOv8 model for real-time edge frame inference."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        imgsz: int = 640,
        confidence: Optional[float] = None,
    ):
        settings = get_settings()
        self.imgsz = imgsz
        self.conf = confidence if confidence is not None else settings.confidence_threshold
        self.model_path = self._resolve_model_path(model_path or settings.default_model)

        self.model = None
        self.enabled = YOLO is not None

        if not self.enabled:
            log.warning("Ultralytics YOLO not installed in this environment; running in mock mode.")
        elif self.model_path and os.path.exists(self.model_path):
            try:
                log.info("Loading YOLO model from %s (imgsz=%d, conf=%.2f)...", self.model_path, self.imgsz, self.conf)
                self.model = YOLO(self.model_path)
                log.info("Model loaded successfully. Classes: %s", getattr(self.model, "names", {}))
            except Exception as exc:
                log.error("Failed to load YOLO model: %s", exc)
                self.model = None
        else:
            log.warning("Model file not found at %s", self.model_path)

    def _resolve_model_path(self, path_str: str) -> str:
        """Resolve model path relative to repo root or shared models directory."""
        settings = get_settings()
        p = Path(path_str)
        if p.is_file():
            return str(p.resolve())

        # Check repo root
        root_path = settings.repo_root / path_str
        if root_path.is_file():
            return str(root_path.resolve())

        # Check shared/models
        shared_path = settings.repo_root / "shared" / "models" / path_str
        if shared_path.is_file():
            return str(shared_path.resolve())

        # Fallback to yolov8n.pt if best_weapon is missing
        fallback = settings.repo_root / "yolov8n.pt"
        if fallback.is_file():
            log.warning("Preferred model %s not found; falling back to %s", path_str, fallback)
            return str(fallback.resolve())

        return path_str

    def infer(self, frame: np.ndarray) -> Tuple[np.ndarray, List[Detection]]:
        """
        Run inference on an OpenCV BGR frame.
        Returns (annotated_frame, list_of_detections).
        """
        if not self.enabled or self.model is None:
            annotated = frame.copy()
            cv2.putText(
                annotated,
                "YOLO UNAVAILABLE (MOCK)",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 165, 255),
                2,
            )
            return annotated, []

        try:
            results = self.model.predict(
                frame,
                imgsz=self.imgsz,
                conf=self.conf,
                verbose=False,
            )
            result = results[0]
            annotated = result.plot()

            detections: List[Detection] = []
            if result.boxes is not None and result.boxes.cls is not None:
                xyxy = result.boxes.xyxy
                cls_list = result.boxes.cls
                conf_list = result.boxes.conf

                try:
                    xyxy = xyxy.cpu().numpy()
                    cls_list = cls_list.cpu().numpy()
                    conf_list = conf_list.cpu().numpy()
                except Exception:
                    xyxy = np.array(xyxy)
                    cls_list = np.array(cls_list)
                    conf_list = np.array(conf_list)

                for box, cls_id, conf in zip(xyxy.tolist(), cls_list.tolist(), conf_list.tolist()):
                    label = self.model.names.get(int(cls_id), str(cls_id))
                    detections.append(
                        Detection(
                            label=str(label),
                            confidence=float(conf),
                            bbox=(int(box[0]), int(box[1]), int(box[2]), int(box[3])),
                        )
                    )

            return annotated, detections

        except Exception as exc:
            log.error("Inference exception: %s", exc)
            return frame.copy(), []
