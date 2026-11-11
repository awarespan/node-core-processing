"""
AWARESPAN — Reusable Media Source Abstraction
Permanent module for registering, tracking, and managing media sources.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class SourceType(str, Enum):
    CAMERA = "CAMERA"
    MICROPHONE = "MICROPHONE"
    COMBINED = "COMBINED"


class SourceOrigin(str, Enum):
    BROWSER_VOLUNTEER = "BROWSER_VOLUNTEER"
    USB_CAMERA = "USB_CAMERA"
    CSI_CAMERA = "CSI_CAMERA"
    USB_MICROPHONE = "USB_MICROPHONE"
    RTSP_STREAM = "RTSP_STREAM"
    SYNTHETIC = "SYNTHETIC"


class SourceState(str, Enum):
    REGISTERED = "REGISTERED"
    AUTHENTICATING = "AUTHENTICATING"
    CONNECTING = "CONNECTING"
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    DISCONNECTING = "DISCONNECTING"
    DISCONNECTED = "DISCONNECTED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


class MediaSource:
    """Represents a registered media source connected to the edge node."""

    def __init__(
        self,
        source_id: str,
        source_type: SourceType,
        source_origin: Optional[SourceOrigin] = None,
        node_id: str = "node-pi5",
        display_name: str = "",
        friendly_name: Optional[str] = None,
        origin: Optional[SourceOrigin] = None,
        state: Optional[SourceState] = None,
        session_id: Optional[str] = None,
        connection_state: Optional[SourceState] = None,
        transport: str = "websocket_binary",
        camera_active: bool = False,
        mic_active: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.source_id = source_id
        self.source_type = source_type
        self.source_origin = origin or source_origin or SourceOrigin.BROWSER_VOLUNTEER
        self.node_id = node_id
        self.display_name = friendly_name or display_name or source_id
        self.session_id = session_id
        self.connection_state = state or connection_state or SourceState.REGISTERED
        self.connected_at: Optional[str] = None
        self.last_seen_at: float = time.time()
        self.disconnected_at: Optional[str] = None
        self.transport = transport
        self.camera_active = camera_active
        self.mic_active = mic_active
        self.capabilities: Dict[str, Any] = {}
        self.metadata = metadata or {}
        self.metrics: Dict[str, Any] = {
            "frames_received": 0,
            "frames_dropped": 0,
            "audio_chunks_received": 0,
            "bytes_received": 0,
            "last_frame_id": 0,
            "last_latency_ms": 0,
        }

    @property
    def origin(self) -> SourceOrigin:
        return self.source_origin

    @property
    def state(self) -> SourceState:
        return self.connection_state

    @state.setter
    def state(self, val: SourceState):
        self.connection_state = val

    @property
    def is_active(self) -> bool:
        return self.connection_state == SourceState.ACTIVE

    @property
    def friendly_name(self) -> str:
        return self.display_name

    @property
    def frames_received(self) -> int:
        return self.metrics.get("frames_received", 0)

    @property
    def audio_packets_received(self) -> int:
        return self.metrics.get("audio_chunks_received", 0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "node_id": self.node_id,
            "source_type": self.source_type.value,
            "source_origin": self.source_origin.value,
            "display_name": self.display_name,
            "session_id": self.session_id,
            "connection_state": self.connection_state.value,
            "connected_at": self.connected_at,
            "last_seen_at": self.last_seen_at,
            "disconnected_at": self.disconnected_at,
            "transport": self.transport,
            "camera_active": self.camera_active,
            "mic_active": self.mic_active,
            "metrics": self.metrics,
            "metadata": self.metadata,
        }

    def record_heartbeat(self) -> None:
        self.last_seen_at = time.time()

    def record_frame(self, frame_id: int, byte_count: int, latency_ms: int = 0) -> None:
        self.last_seen_at = time.time()
        self.metrics["frames_received"] += 1
        self.metrics["bytes_received"] += byte_count
        self.metrics["last_frame_id"] = frame_id
        self.metrics["last_latency_ms"] = latency_ms

    def record_frame_drop(self) -> None:
        self.metrics["frames_dropped"] += 1

    def record_audio_chunk(self, byte_count: int) -> None:
        self.last_seen_at = time.time()
        self.metrics["audio_chunks_received"] += 1
        self.metrics["bytes_received"] += byte_count
