"""
AWARESPAN — Frame Ingestion & Buffer
Bounded FIFO queues with backpressure, timestamp preservation, and efficient OpenCV frame decoding.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import asyncio
import base64
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

try:
    import cv2
except ImportError:
    cv2 = None

import numpy as np

from shared.logging.logger import get_logger

log = get_logger("node_runtime.media.frame_buffer")


class FramePacket:
    """Carries an ingested camera frame with source attribution and timestamps."""

    def __init__(
        self,
        source_id: str,
        frame_id: int = 0,
        source_ts_ms: int = 0,
        ingest_ts_ms: int = 0,
        jpeg_bytes: bytes = b"",
        width: Optional[int] = None,
        height: Optional[int] = None,
        # Backward/cross-compatibility kwargs
        sequence: Optional[int] = None,
        timestamp_ms: Optional[int] = None,
        payload: Optional[bytes] = None,
    ):
        self.source_id = source_id
        self.frame_id = sequence if sequence is not None else frame_id
        self.source_ts_ms = timestamp_ms if timestamp_ms is not None else (source_ts_ms or int(time.time() * 1000))
        self.ingest_ts_ms = ingest_ts_ms or int(time.time() * 1000)
        self.jpeg_bytes = payload if payload is not None else jpeg_bytes
        self.width = width
        self.height = height

    @property
    def sequence(self) -> int:
        return self.frame_id

    @property
    def timestamp_ms(self) -> int:
        return self.source_ts_ms

    @property
    def payload(self) -> bytes:
        return self.jpeg_bytes

    def decode(self, max_dim: int = 1280) -> Optional[np.ndarray]:
        """Decode JPEG bytes into an OpenCV BGR numpy array with optional downscale clamp."""
        if not self.jpeg_bytes:
            return None
        if cv2 is None:
            # Fallback if cv2 is not installed in runtime environment
            try:
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(self.jpeg_bytes)).convert("RGB")
                arr = np.array(img)
                # Convert RGB to BGR
                return arr[:, :, ::-1]
            except Exception:
                return None

        try:
            arr = np.frombuffer(self.jpeg_bytes, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                return None

            h, w = frame.shape[:2]
            if max(h, w) > max_dim:
                scale = max_dim / float(max(h, w))
                new_w, new_h = int(w * scale), int(h * scale)
                frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

            return frame
        except Exception as exc:
            log.warning("Frame decode failure for source %s: %s", self.source_id, exc)
            return None


class SourceFrameBuffer:
    """Bounded, thread-safe frame queue with backpressure for an individual media source."""

    def __init__(self, source_id: str = "default", max_capacity: int = 3, max_size: Optional[int] = None):
        self.source_id = source_id
        self.max_capacity = max_size if max_size is not None else max_capacity
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=self.max_capacity)
        self.frames_received: int = 0
        self.frames_dropped: int = 0

    @property
    def size(self) -> int:
        return self.queue.qsize()

    @property
    def dropped_frames(self) -> int:
        return self.frames_dropped

    def push(self, packet: FramePacket) -> bool:
        """Alias for put_frame."""
        return self.put_frame(packet)

    def pop(self) -> Optional[FramePacket]:
        """Synchronous non-blocking pop if available."""
        try:
            return self.queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    def put_frame(self, packet: FramePacket) -> bool:
        """
        Enqueues a frame. If queue is full, drops the oldest frame (FIFO backpressure).
        """
        self.frames_received += 1
        if self.queue.full():
            try:
                self.queue.get_nowait()
                self.frames_dropped += 1
            except asyncio.QueueEmpty:
                pass

        try:
            self.queue.put_nowait(packet)
            return True
        except asyncio.QueueFull:
            self.frames_dropped += 1
            return False

    async def get_frame(self, timeout_sec: float = 1.0) -> Optional[FramePacket]:
        """Awaits next available frame packet."""
        try:
            return await asyncio.wait_for(self.queue.get(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            return None


class MediaFrameBufferManager:
    """Manages independent frame buffers for all registered media sources."""

    def __init__(self, default_buffer_size: int = 3):
        self.default_buffer_size = default_buffer_size
        self._buffers: Dict[str, SourceFrameBuffer] = {}

    def get_or_create(self, source_id: str) -> SourceFrameBuffer:
        if source_id not in self._buffers:
            self._buffers[source_id] = SourceFrameBuffer(
                source_id=source_id,
                max_capacity=self.default_buffer_size,
            )
        return self._buffers[source_id]

    def ingest_raw_frame(
        self,
        source_id: str,
        frame_id: int,
        source_ts_ms: int,
        jpeg_bytes: bytes,
    ) -> bool:
        pkt = FramePacket(
            source_id=source_id,
            frame_id=frame_id,
            source_ts_ms=source_ts_ms,
            jpeg_bytes=jpeg_bytes,
        )
        buf = self.get_or_create(source_id)
        return buf.put_frame(pkt)

    async def get_next_frame(self, timeout_sec: float = 0.5) -> Optional[FramePacket]:
        for buf in list(self._buffers.values()):
            try:
                return buf.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        await asyncio.sleep(0.01)
        return None

    def remove(self, source_id: str) -> None:
        if source_id in self._buffers:
            del self._buffers[source_id]

    def clear(self) -> None:
        self._buffers.clear()


# Class aliases for convenience
FrameBuffer = SourceFrameBuffer
MultiSourceFrameIngestion = MediaFrameBufferManager
