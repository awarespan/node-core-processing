"""
AWARESPAN — Core Media Router
Routes multi-source video and audio streams into the inference engine with strict source attribution.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import asyncio
import time
from typing import Callable, Dict, Optional, Tuple

import numpy as np

from shared.logging.logger import get_logger
from node_runtime.media.ingestion.audio_buffer import MultiSourceAudioIngestion
from node_runtime.media.ingestion.frame_buffer import FramePacket, MultiSourceFrameIngestion
from node_runtime.media.registry.source_registry import MediaSourceRegistry, get_source_registry
from node_runtime.media.sources.source import SourceState

log = get_logger("node_runtime.media.router")


class CoreMediaRouter:
    """Central router coordinating multi-source media ingestion and inference delivery."""

    def __init__(
        self,
        registry: Optional[MediaSourceRegistry] = None,
        frame_ingestion: Optional[MultiSourceFrameIngestion] = None,
        audio_ingestion: Optional[MultiSourceAudioIngestion] = None,
    ):
        self.registry = registry or get_source_registry()
        self.frame_ingestion = frame_ingestion or MultiSourceFrameIngestion()
        self.audio_ingestion = audio_ingestion or MultiSourceAudioIngestion()
        self._inference_callback: Optional[Callable[[np.ndarray, str, int, int], None]] = None
        self._frame_handler: Optional[Callable] = None

    def register_inference_handler(self, callback: Callable[[np.ndarray, str, int, int], None]) -> None:
        """Register the downstream inference pipeline handler (frame, source_id, frame_id, ts_ms)."""
        self._inference_callback = callback

    def register_frame_handler(self, callback: Callable) -> None:
        """Register frame handler receiving (FramePacket, frame_ndarray)."""
        self._frame_handler = callback

    def route_frame(self, packet: FramePacket, source: Optional[Any] = None) -> bool:
        """Route frame packet from any source to registered frame or inference handler."""
        src_id = packet.source_id
        src = source or self.registry.get_source(src_id)
        if src and src.connection_state == SourceState.CONNECTING:
            if hasattr(self.registry, "state_machine"):
                self.registry.state_machine.transition(src, SourceState.ACTIVE)
            else:
                self.registry.update_state(src_id, SourceState.ACTIVE)
        if src:
            src.camera_active = True
            src.record_frame(packet.sequence, len(packet.payload))

        decoded = packet.decode()
        if self._frame_handler:
            self._frame_handler(packet, decoded)
        elif self._inference_callback and decoded is not None:
            self._inference_callback(decoded, packet.source_id, packet.sequence, packet.timestamp_ms)

        return True

    def ingest_frame(
        self,
        source_id: str,
        frame_id: int,
        source_ts_ms: int,
        jpeg_bytes: bytes,
    ) -> bool:
        """
        Ingest a raw JPEG camera frame from a source.
        Validates source state and activates source on first valid frame.
        """
        source = self.registry.get_source(source_id)
        if not source:
            log.warning("Dropping frame: unregistered source %s", source_id)
            return False

        if source.connection_state == SourceState.CONNECTING:
            self.registry.update_state(source_id, SourceState.ACTIVE, reason="First valid frame received")

        source.camera_active = True
        source.record_frame(frame_id, len(jpeg_bytes))

        return self.frame_ingestion.ingest_raw_frame(source_id, frame_id, source_ts_ms, jpeg_bytes)

    def ingest_audio(
        self,
        source_id: str,
        source_ts_ms: int,
        pcm_bytes: bytes,
        sample_rate: int = 16000,
        fmt: str = "pcm_s16le",
    ) -> bool:
        """
        Ingest audio samples from a microphone source.
        """
        source = self.registry.get_source(source_id)
        if not source:
            log.warning("Dropping audio: unregistered source %s", source_id)
            return False

        if source.connection_state == SourceState.CONNECTING:
            self.registry.update_state(source_id, SourceState.ACTIVE, reason="First audio chunk received")

        source.mic_active = True
        source.record_audio_chunk(len(pcm_bytes))

        return self.audio_ingestion.ingest_pcm_chunk(source_id, source_ts_ms, pcm_bytes, sample_rate, fmt)

    async def run_dispatch_loop(self) -> None:
        """
        Background loop reading from frame buffer and invoking downstream inference.
        """
        log.info("Media router dispatch loop active")
        while True:
            packet: Optional[FramePacket] = await self.frame_ingestion.get_next_frame()
            if not packet:
                continue

            frame = packet.decode()
            if frame is None:
                continue

            if self._inference_callback:
                try:
                    self._inference_callback(
                        frame,
                        packet.source_id,
                        packet.frame_id,
                        packet.source_ts_ms,
                    )
                except Exception as exc:
                    log.warning("Inference dispatch error for source %s: %s", packet.source_id, exc)


_GLOBAL_MEDIA_ROUTER: Optional[CoreMediaRouter] = None


def get_media_router() -> CoreMediaRouter:
    """Singleton getter for CoreMediaRouter."""
    global _GLOBAL_MEDIA_ROUTER
    if _GLOBAL_MEDIA_ROUTER is None:
        _GLOBAL_MEDIA_ROUTER = CoreMediaRouter()
    return _GLOBAL_MEDIA_ROUTER
