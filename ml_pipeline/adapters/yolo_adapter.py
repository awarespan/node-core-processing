"""
AWARESPAN — YOLOv8 Model Adapter
Provides framework-level integration with Ultralytics YOLOv8 for edge visual inference.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import os
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from shared.logging.logger import get_logger
from ml_pipeline.adapters.base import ThreatModelAdapter
from ml_pipeline.schema.predictions import StandardDetectionPrediction, StandardModelPrediction
from ml_pipeline.taxonomy.taxonomy_manager import get_taxonomy_manager

log = get_logger("ml_pipeline.adapters.yolo")

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None


class YOLOv8Adapter(ThreatModelAdapter):
    """Adapter for Ultralytics YOLOv8 object detection models."""

    def __init__(
        self,
        model_id: str = "awarespan-weapon-yolov8n",
        model_version: str = "1.0.0",
        taxonomy_version: str = "1.0.0",
    ):
        super().__init__(model_id, model_version, taxonomy_version)
        self.model: Optional[Any] = None
        self.classes: Dict[int, str] = {}
        self.imgsz: int = 640
        self.conf: float = 0.40
        self.device: str = "cpu"
        self.taxonomy = get_taxonomy_manager()

    def load(self, artifact_path: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """Load YOLOv8 weights from disk."""
        if YOLO is None:
            log.warning("Ultralytics library not available in current environment.")
            return False

        if not os.path.isfile(artifact_path):
            log.error("Artifact path does not exist: %s", artifact_path)
            return False

        self.config = config or {}
        self.imgsz = int(self.config.get("imgsz", 640))
        self.conf = float(self.config.get("conf", 0.40))
        self.device = str(self.config.get("device", "cpu"))
        self.artifact_path = artifact_path

        try:
            log.info("Loading YOLOv8 weights from %s (imgsz=%d, conf=%.2f)...", artifact_path, self.imgsz, self.conf)
            self.model = YOLO(artifact_path)
            self.classes = getattr(self.model, "names", {})
            self.is_loaded = True
            log.info("YOLOv8 adapter ready with %d classes: %s", len(self.classes), self.classes)
            return True
        except Exception as exc:
            log.error("Failed to load YOLOv8 model from %s: %s", artifact_path, exc)
            self.model = None
            self.is_loaded = False
            return False

    def predict(self, input_data: Any) -> StandardModelPrediction:
        """
        Run object detection on an image input (numpy BGR frame or image path).
        """
        t0 = time.perf_counter()

        if not self.is_loaded or self.model is None:
            # Fallback mock prediction when running without weights loaded
            latency_ms = (time.perf_counter() - t0) * 1000.0
            return StandardModelPrediction(
                model_id=self.model_id,
                model_version=self.model_version,
                modality="visual",
                task="object_detection",
                taxonomy_version=self.taxonomy_version,
                predictions=[],
                inference_latency_ms=latency_ms,
                device=self.device,
                metadata={"status": "unloaded_mock"},
            )

        # Execute inference
        res = self.model.predict(
            source=input_data,
            imgsz=self.imgsz,
            conf=self.conf,
            device=self.device,
            verbose=False,
        )

        detections: List[StandardDetectionPrediction] = []
        resolution = None

        if res and len(res) > 0:
            result = res[0]
            if hasattr(result, "orig_shape") and result.orig_shape:
                resolution = (result.orig_shape[0], result.orig_shape[1])

            boxes = result.boxes
            if boxes is not None:
                for box in boxes:
                    cls_id = int(box.cls[0].item())
                    conf = float(box.conf[0].item())
                    xyxy = box.xyxy[0].tolist()
                    bbox = [int(round(coord)) for coord in xyxy]

                    raw_label = self.classes.get(cls_id, str(cls_id))
                    taxonomy_class = self.taxonomy.map_raw_label(raw_label, modality="visual")

                    detections.append(
                        StandardDetectionPrediction(
                            class_id=taxonomy_class,
                            confidence=round(conf, 4),
                            raw_label=raw_label,
                            bounding_box=bbox,
                            metadata={"class_index": cls_id},
                        )
                    )

        latency_ms = (time.perf_counter() - t0) * 1000.0

        return StandardModelPrediction(
            model_id=self.model_id,
            model_version=self.model_version,
            modality="visual",
            task="object_detection",
            taxonomy_version=self.taxonomy_version,
            predictions=detections,
            inference_latency_ms=round(latency_ms, 2),
            input_resolution=resolution,
            device=self.device,
        )

    def metadata(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "framework": "ultralytics_yolov8",
            "artifact_path": self.artifact_path,
            "is_loaded": self.is_loaded,
            "classes": self.classes,
            "imgsz": self.imgsz,
            "conf": self.conf,
            "device": self.device,
        }

    def health_check(self) -> bool:
        if not self.is_loaded or self.model is None:
            return False
        try:
            # Test inference on a 64x64 blank image
            dummy = np.zeros((64, 64, 3), dtype=np.uint8)
            pred = self.predict(dummy)
            return isinstance(pred, StandardModelPrediction)
        except Exception as exc:
            log.warning("Health check failed for %s: %s", self.model_id, exc)
            return False
