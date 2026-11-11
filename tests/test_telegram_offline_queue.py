"""
AWARESPAN — Telegram Source Lifecycle & Offline Queue Unit Tests
Tests lifecycle notifications, offline SQLite queue persistence, and FIFO queue drainage.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import time
import pytest
from unittest.mock import patch

from node_runtime.media.sources.source import MediaSource, SourceOrigin, SourceState, SourceType
from node_runtime.media.lifecycle.state_machine import SourceStateMachine
from node_runtime.monitoring.telegram_lifecycle import TelegramLifecycleNotifier


def test_telegram_label_formatting(tmp_path):
    db_file = tmp_path / "telegram_queue.db"
    notifier = TelegramLifecycleNotifier(db_path=str(db_file))

    # Test Camera only
    src1 = MediaSource(source_id="s1", source_type=SourceType.CAMERA, origin=SourceOrigin.BROWSER_VOLUNTEER)
    src1.camera_active = True
    assert notifier.format_source_label(src1) == "Camera"

    # Test Mic only
    src2 = MediaSource(source_id="s2", source_type=SourceType.MICROPHONE, origin=SourceOrigin.BROWSER_VOLUNTEER)
    src2.mic_active = True
    assert notifier.format_source_label(src2) == "Microphone"

    # Test Combined
    src3 = MediaSource(source_id="s3", source_type=SourceType.COMBINED, origin=SourceOrigin.BROWSER_VOLUNTEER)
    src3.camera_active = True
    src3.mic_active = True
    assert notifier.format_source_label(src3) == "Camera + Microphone"


def test_telegram_offline_queue_persistence(tmp_path):
    db_file = tmp_path / "telegram_queue.db"
    notifier = TelegramLifecycleNotifier(db_path=str(db_file))

    # Mock send_message to always fail (simulating offline node)
    with patch("node_runtime.monitoring.telegram_lifecycle.send_message", return_value=False):
        res = notifier.dispatch_or_queue("Test offline alert")
        assert res is False
        assert notifier.get_pending_count() == 1

        notifier.dispatch_or_queue("Second offline alert")
        assert notifier.get_pending_count() == 2


def test_telegram_state_transition_integration(tmp_path):
    db_file = tmp_path / "telegram_queue.db"
    notifier = TelegramLifecycleNotifier(db_path=str(db_file))
    sm = SourceStateMachine()
    sm.add_listener(notifier.on_source_transition)

    source = MediaSource(
        source_id="vol-pixel",
        source_type=SourceType.CAMERA,
        origin=SourceOrigin.BROWSER_VOLUNTEER,
        friendly_name="Pixel 7 Pro",
    )
    source.camera_active = True

    with patch("node_runtime.monitoring.telegram_lifecycle.send_message", return_value=False):
        # Transition: REGISTERED -> AUTHENTICATING -> CONNECTING -> ACTIVE
        sm.transition(source, SourceState.AUTHENTICATING)
        sm.transition(source, SourceState.CONNECTING)
        sm.transition(source, SourceState.ACTIVE)

        # Should have enqueued 1 connection message
        assert notifier.get_pending_count() == 1

        # Transition: ACTIVE -> DISCONNECTED
        sm.transition(source, SourceState.DISCONNECTED)
        assert notifier.get_pending_count() == 2


def test_telegram_queue_drain(tmp_path):
    db_file = tmp_path / "telegram_queue.db"
    notifier = TelegramLifecycleNotifier(db_path=str(db_file))

    # Pre-enqueue 2 items
    notifier._enqueue("Message 1")
    notifier._enqueue("Message 2")
    assert notifier.get_pending_count() == 2

    sent_messages = []

    def mock_send(text, chat_id=None):
        sent_messages.append(text)
        return True

    with patch("node_runtime.monitoring.telegram_lifecycle.send_message", side_effect=mock_send):
        # Start worker briefly to drain
        notifier.start()
        notifier._wake_event.set()
        for _ in range(40):
            if notifier.get_pending_count() == 0:
                break
            time.sleep(0.1)
        notifier.stop()

    assert notifier.get_pending_count() == 0
    assert len(sent_messages) == 2
    assert sent_messages[0] == "Message 1"
    assert sent_messages[1] == "Message 2"
