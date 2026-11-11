"""
AWARESPAN — Shared Data Models
Structured data classes for detections, threat events, heartbeats, and updates.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Detection:
    """A single object detection result from an inference model."""
    label: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ThreatEvent:
    """A classified threat event evaluated by the threat assessment pipeline."""
    event_id: str
    ts_ms: int
    tier: str  # "tier1" | "tier2" | "none"
    labels: List[str]
    max_confidence: float
    action: str  # "siren" | "alert" | "led" | "silent" | "none"
    latency_ms: int = 0
    frame_id: int = 0
    model: str = ""
    source_id: str = "builtin"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NodeHeartbeat:
    """Telemetry heartbeat published periodically to MQTT and backend REST."""
    node_id: str
    ts_ms: int
    status: str = "ONLINE"
    cpu_temp_c: Optional[float] = None
    throttled_hex: Optional[str] = None
    undervoltage: bool = False
    queue_depth: int = 0
    active_model: str = ""
    version: str = "2.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PowerStatus:
    """Hardware power and thermal status for Raspberry Pi."""
    throttled_raw: str
    undervoltage_now: bool
    undervoltage_occurred: bool
    freq_capped_now: bool
    freq_capped_occurred: bool
    temp_c: Optional[float]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UpdateState:
    """Persistent state tracking for the automatic node updater."""
    current_commit: str = "unknown"
    target_commit: str = ""
    status: str = "IDLE"  # "IDLE" | "CHECKING" | "UPDATING" | "SUCCESS" | "ROLLED_BACK" | "FAILED"
    last_check: str = ""
    last_update: str = ""
    last_error: str = ""
    rollback_target: str = ""
    history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ModelMetadata:
    """Metadata specification for approved production model artifacts."""
    model_name: str
    version: str
    classes: List[str]
    num_classes: int
    input_resolution: List[int]
    confidence_threshold: float
    sha256: str
    created_at: str
    target_hardware: str = "Raspberry Pi 5"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
