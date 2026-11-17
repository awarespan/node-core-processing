"""Temporal video adapter contract for future human-action recognition models.

This module defines the sequence-level interface only. No video weights are
bundled and no classifier is claimed to be active until an implementation is
registered, audited, and loaded.
"""

from typing import Any, Dict, List, Optional, Sequence

from ml_pipeline.adapters.base import ThreatModelAdapter
from ml_pipeline.schema.predictions import StandardModelPrediction


class TemporalVideoAdapter(ThreatModelAdapter):
    """Base adapter for models that need ordered frames, not isolated images."""

    def __init__(self, model_id: str = "awarespan-human-video-actions", **kwargs):
        super().__init__(model_id=model_id, **kwargs)
        self.frames_per_clip = 16
        self.sample_fps = 4.0
        self.input_size = (224, 224)
        self.class_map: Dict[int, str] = {}

    def load(self, artifact_path: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """Concrete video backends must implement model-specific loading."""
        raise NotImplementedError("No temporal video backend is configured yet")

    def predict(self, input_data: Any) -> StandardModelPrediction:
        """Accept an ordered sequence of frames with timestamps from one clip."""
        if not isinstance(input_data, Sequence) or isinstance(input_data, (str, bytes)):
            raise TypeError("Video inference requires an ordered sequence of frame records")
        if len(input_data) != self.frames_per_clip:
            raise ValueError(f"Expected {self.frames_per_clip} frames, received {len(input_data)}")
        raise NotImplementedError("Register a validated temporal model backend before enabling video inference")

    def metadata(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "framework": "temporal_backend_pending",
            "modality": "video",
            "task": "temporal_action_recognition",
            "frames_per_clip": self.frames_per_clip,
            "sample_fps": self.sample_fps,
            "input_size": self.input_size,
            "is_loaded": self.is_loaded,
        }

    def health_check(self) -> bool:
        return False
