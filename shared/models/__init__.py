"""AWARESPAN Data Models Package."""
from .events import (
    Detection,
    ThreatEvent,
    NodeHeartbeat,
    PowerStatus,
    UpdateState,
    ModelMetadata,
)

__all__ = [
    "Detection",
    "ThreatEvent",
    "NodeHeartbeat",
    "PowerStatus",
    "UpdateState",
    "ModelMetadata",
]
