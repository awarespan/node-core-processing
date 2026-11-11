"""
AWARESPAN — Audio Ingestion & Buffer
Bounded audio buffers for volunteer microphone streams.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from shared.logging.logger import get_logger

log = get_logger("node_runtime.media.audio_buffer")


class AudioPacket:
    def __init__(
        self,
        source_id: str,
        source_ts_ms: int = 0,
        ingest_ts_ms: int = 0,
        pcm_bytes: bytes = b"",
        sample_rate: int = 16000,
        format: str = "pcm_s16le",
        sequence: int = 0,
        timestamp_ms: Optional[int] = None,
        payload: Optional[bytes] = None,
        channels: int = 1,
    ):
        self.source_id = source_id
        self.source_ts_ms = timestamp_ms if timestamp_ms is not None else (source_ts_ms or int(time.time() * 1000))
        self.ingest_ts_ms = ingest_ts_ms or int(time.time() * 1000)
        self.pcm_bytes = payload if payload is not None else pcm_bytes
        self.sample_rate = sample_rate
        self.format = format
        self.sequence = sequence
        self.channels = channels

    @property
    def payload(self) -> bytes:
        return self.pcm_bytes

    def to_float32(self) -> np.ndarray:
        """Convert raw PCM bytes to normalized 1D float32 numpy array."""
        if not self.pcm_bytes:
            return np.array([], dtype=np.float32)
        try:
            if self.format == "pcm_s16le":
                arr = np.frombuffer(self.pcm_bytes, dtype=np.int16)
                return arr.astype(np.float32) / 32768.0
            elif self.format == "pcm_f32le":
                return np.frombuffer(self.pcm_bytes, dtype=np.float32)
            else:
                return np.array([], dtype=np.float32)
        except Exception as exc:
            log.warning("Audio conversion failure for source %s: %s", self.source_id, exc)
            return np.array([], dtype=np.float32)


class AudioBuffer:
    """Individual audio buffer for a single source."""

    def __init__(self, sample_rate: int = 16000, max_duration_sec: float = 3.0):
        self.sample_rate = sample_rate
        self.max_duration_sec = max_duration_sec
        self.packets: List[AudioPacket] = []

    @property
    def total_samples(self) -> int:
        return sum(len(p.pcm_bytes) // 2 for p in self.packets)

    def push(self, packet: AudioPacket) -> None:
        self.packets.append(packet)
        now_ms = int(time.time() * 1000)
        cutoff = now_ms - int(self.max_duration_sec * 1000)
        self.packets = [p for p in self.packets if p.ingest_ts_ms >= cutoff]

    def get_window(self, duration_sec: float = 1.0) -> Optional[np.ndarray]:
        if not self.packets:
            return None
        samples_list = [p.to_float32() for p in self.packets if len(p.pcm_bytes) > 0]
        if not samples_list:
            return None
        merged = np.concatenate(samples_list)
        target_len = int(duration_sec * self.sample_rate)
        if len(merged) > target_len:
            merged = merged[-target_len:]
        return merged


class MultiSourceAudioIngestion:
    """Manages audio streams and rolling sample windows across all microphone sources."""

    def __init__(self, max_buffer_sec: float = 3.0):
        self.max_buffer_sec = max_buffer_sec
        self._buffers: Dict[str, AudioBuffer] = {}

    def ingest_pcm_chunk(
        self,
        source_id: str,
        source_ts_ms: int,
        pcm_bytes: bytes,
        sample_rate: int = 16000,
        fmt: str = "pcm_s16le",
    ) -> bool:
        """Ingest a chunk of audio samples."""
        packet = AudioPacket(
            source_id=source_id,
            source_ts_ms=source_ts_ms,
            ingest_ts_ms=int(time.time() * 1000),
            pcm_bytes=pcm_bytes,
            sample_rate=sample_rate,
            format=fmt,
        )

        if source_id not in self._buffers:
            self._buffers[source_id] = AudioBuffer(sample_rate=sample_rate, max_duration_sec=self.max_buffer_sec)

        self._buffers[source_id].push(packet)
        return True

    def get_latest_window(self, source_id: str, duration_sec: float = 1.0) -> Optional[np.ndarray]:
        """Aggregate recent audio packets for a source into a unified 1D float32 buffer."""
        buf = self._buffers.get(source_id)
        if not buf:
            return None
        return buf.get_window(duration_sec=duration_sec)

    def remove_source(self, source_id: str) -> None:
        if source_id in self._buffers:
            del self._buffers[source_id]
