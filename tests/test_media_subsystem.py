"""
AWARESPAN — Core Media Subsystem Unit Tests
Tests source registration, state transitions, frame/audio buffers, and media routing.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import time
import numpy as np
import pytest

from node_runtime.media.sources.source import MediaSource, SourceOrigin, SourceState, SourceType
from node_runtime.media.lifecycle.state_machine import SourceStateMachine
from node_runtime.media.registry.source_registry import MediaSourceRegistry
from node_runtime.media.ingestion.frame_buffer import FrameBuffer, FramePacket
from node_runtime.media.ingestion.audio_buffer import AudioBuffer, AudioPacket
from node_runtime.media.routing.media_router import CoreMediaRouter


def test_media_source_creation():
    source = MediaSource(
        source_id="cam-01",
        source_type=SourceType.CAMERA,
        origin=SourceOrigin.BROWSER_VOLUNTEER,
        friendly_name="Volunteer Pixel",
    )
    assert source.source_id == "cam-01"
    assert source.state == SourceState.REGISTERED
    assert source.is_active is False
    assert source.friendly_name == "Volunteer Pixel"


def test_state_machine_valid_transitions():
    sm = SourceStateMachine()
    source = MediaSource(
        source_id="src-01",
        source_type=SourceType.CAMERA,
        origin=SourceOrigin.BROWSER_VOLUNTEER,
    )

    # REGISTERED -> AUTHENTICATING
    assert sm.transition(source, SourceState.AUTHENTICATING) is True
    assert source.state == SourceState.AUTHENTICATING

    # AUTHENTICATING -> CONNECTING
    assert sm.transition(source, SourceState.CONNECTING) is True
    assert source.state == SourceState.CONNECTING

    # CONNECTING -> ACTIVE
    assert sm.transition(source, SourceState.ACTIVE) is True
    assert source.state == SourceState.ACTIVE
    assert source.is_active is True

    # ACTIVE -> DISCONNECTED
    assert sm.transition(source, SourceState.DISCONNECTED) is True
    assert source.state == SourceState.DISCONNECTED
    assert source.is_active is False


def test_state_machine_invalid_transitions():
    sm = SourceStateMachine()
    source = MediaSource(
        source_id="src-02",
        source_type=SourceType.MICROPHONE,
        origin=SourceOrigin.BROWSER_VOLUNTEER,
    )
    # Cannot jump from REGISTERED directly to ACTIVE without bypass
    assert sm.transition(source, SourceState.ACTIVE) is False
    assert source.state == SourceState.REGISTERED


def test_source_registry_registration_and_cleanup():
    registry = MediaSourceRegistry()
    source = MediaSource(
        source_id="vol-test-1",
        source_type=SourceType.COMBINED,
        origin=SourceOrigin.BROWSER_VOLUNTEER,
    )
    assert registry.register_source(source) is True
    assert registry.get_source("vol-test-1") is not None
    assert len(registry.get_all_sources()) == 1

    # Update heartbeat
    registry.update_heartbeat("vol-test-1")

    # Deregister
    assert registry.deregister_source("vol-test-1") is True
    assert registry.get_source("vol-test-1") is None
    assert len(registry.get_all_sources()) == 0


def test_frame_buffer_backpressure():
    buffer = FrameBuffer(max_size=3)
    # Push 5 frames
    for i in range(5):
        pkt = FramePacket(
            source_id="cam-01",
            sequence=i,
            timestamp_ms=int(time.time() * 1000),
            payload=b"\xff\xd8\xff\xe0" + b"\x00" * 20,
        )
        buffer.push(pkt)

    assert buffer.size == 3
    assert buffer.dropped_frames == 2
    # The oldest frames (0 and 1) were dropped; queue should start at sequence 2
    oldest = buffer.pop()
    assert oldest is not None
    assert oldest.sequence == 2


def test_audio_buffer_windowing():
    buffer = AudioBuffer(sample_rate=16000, max_duration_sec=2.0)
    # Generate 1600 samples (0.1s at 16kHz) of 16-bit PCM
    sine_wave = (np.sin(np.linspace(0, 100, 1600)) * 32767).astype(np.int16)
    pcm_bytes = sine_wave.tobytes()

    pkt = AudioPacket(
        source_id="mic-01",
        sequence=1,
        timestamp_ms=int(time.time() * 1000),
        payload=pcm_bytes,
        sample_rate=16000,
        channels=1,
        format="pcm_s16le",
    )
    buffer.push(pkt)
    assert buffer.total_samples == 1600

    window = buffer.get_window(duration_sec=0.1)
    assert window is not None
    assert len(window) == 1600
    assert isinstance(window, np.ndarray)


def test_core_media_router():
    registry = MediaSourceRegistry()
    router = CoreMediaRouter(registry=registry)

    source = MediaSource(
        source_id="vol-test-cam",
        source_type=SourceType.CAMERA,
        origin=SourceOrigin.BROWSER_VOLUNTEER,
    )
    registry.register_source(source)
    registry.state_machine.transition(source, SourceState.AUTHENTICATING)
    registry.state_machine.transition(source, SourceState.CONNECTING)

    received_frames = []

    def frame_handler(packet, frame):
        received_frames.append((packet.source_id, packet.sequence))

    router.register_frame_handler(frame_handler)

    # Create dummy JPEG
    try:
        import cv2
        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, encoded = cv2.imencode(".jpg", dummy_img)
        jpeg_bytes = bytes(encoded)
    except Exception:
        jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xd9"

    pkt = FramePacket(
        source_id="vol-test-cam",
        sequence=42,
        timestamp_ms=int(time.time() * 1000),
        payload=jpeg_bytes,
    )

    success = router.route_frame(pkt, source)
    assert success is True
    assert len(received_frames) == 1
    assert received_frames[0] == ("vol-test-cam", 42)
    # Router should auto-transition CONNECTING source to ACTIVE
    assert source.state == SourceState.ACTIVE
