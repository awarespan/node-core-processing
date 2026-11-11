"""
AWARESPAN — Mock Threat Model Adapter
Used for deterministic testing, CI verification, and synthetic threat injection.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import time
from typing import Any, Dict, List, Optional

from ml_pipeline.adapters.base import ThreatModelAdapter
from ml_pipeline.schema.predictions import StandardDetectionPrediction, StandardModelPrediction


class MockThreatAdapter(ThreatModelAdapter):
    """Deterministic mock adapter for testing."""

    def __init__(
        self,
        model_id: str = "mock-threat-model",
        model_version: str = "1.0.0",
        modality: str = "visual",
        synthetic_detections: Optional[List[StandardDetectionPrediction]] = None,
    ):
        super().__init__(model_id, model_version)
        self.modality = modality
        self.synthetic_detections = synthetic_detections or []
        self.is_loaded = True

    def load(self, artifact_path: str, config: Optional[Dict[str, Any]] = None) -> bool:
        self.artifact_path = artifact_path
        self.is_loaded = True
        return True

    def predict(self, input_data: Any) -> StandardModelPrediction:
        t0 = time.perf_counter()
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return StandardModelPrediction(
            model_id=self.model_id,
            model_version=self.model_version,
            modality=self.modality,
            task="object_detection" if self.modality == "visual" else "audio_classification",
            taxonomy_version=self.taxonomy_version,
            predictions=self.synthetic_detections,
            inference_latency_ms=round(latency_ms, 2),
            device="mock",
        )

    def metadata(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "modality": self.modality,
            "is_loaded": self.is_loaded,
        }

    def health_check(self) -> bool:
        return True
