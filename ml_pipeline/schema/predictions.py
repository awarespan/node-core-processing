"""
AWARESPAN — Standard Prediction Schema
Vendor- and framework-agnostic prediction representation for all threat intelligence models.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class StandardDetectionPrediction:
    """Represents a single detected entity, action, or acoustic event."""
    class_id: str                          # Taxonomy class ID (e.g. "weapon.firearm.handgun")
    confidence: float                      # Calibrated confidence score (0.0 to 1.0)
    raw_label: str                         # Raw upstream model label (e.g. "gun")
    bounding_box: Optional[List[int]] = None # [x1, y1, x2, y2] pixel coordinates (visual only)
    time_offset_ms: Optional[float] = None  # Offset relative to packet start (temporal/audio)
    duration_ms: Optional[float] = None     # Event duration in milliseconds (audio/action)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StandardModelPrediction:
    """Standardized top-level response returned by any ThreatModelAdapter."""
    model_id: str
    model_version: str
    modality: str                          # "visual", "acoustic", "multimodal"
    task: str                              # "object_detection", "audio_classification", "action_recognition"
    taxonomy_version: str
    predictions: List[StandardDetectionPrediction]
    inference_latency_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    input_resolution: Optional[Tuple[int, int]] = None
    device: str = "cpu"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: Optional[int] = None) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StandardModelPrediction":
        preds_raw = data.get("predictions", [])
        preds = [
            StandardDetectionPrediction(**p) if isinstance(p, dict) else p
            for p in preds_raw
        ]
        data_copy = dict(data)
        data_copy["predictions"] = preds
        return cls(**data_copy)
