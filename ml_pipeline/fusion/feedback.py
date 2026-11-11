"""
AWARESPAN — Human Operator Feedback Subsystem
Preserves ground-truth AI predictions alongside human operator validations and corrections.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.logging.logger import get_logger

log = get_logger("ml_pipeline.fusion.feedback")


@dataclass
class HumanFeedbackRecord:
    feedback_id: str
    assessment_id: str
    operator_id: str
    decision: str                          # "CONFIRMED", "REJECTED_FALSE_POSITIVE", "CORRECTED"
    original_prediction: Dict[str, Any]    # Never mutated
    corrected_class_id: Optional[str] = None
    operator_notes: str = ""
    taxonomy_version: str = "1.0.0"
    model_id: str = ""
    model_version: str = ""
    timestamp_iso: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HumanFeedbackStore:
    """Appends operator feedback without altering ground-truth AI outputs."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.path = storage_path or (Path("state") / "human_feedback.jsonl")

    def record_feedback(self, record: HumanFeedbackRecord) -> bool:
        """Append feedback record to persistent JSONL log."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict()) + "\n")
            log.info("Recorded operator feedback %s for assessment %s (%s)", record.feedback_id, record.assessment_id, record.decision)
            return True
        except Exception as exc:
            log.error("Failed to write human feedback: %s", exc)
            return False
