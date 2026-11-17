"""Pi speaker output tests with ALSA device enumeration and playback mocked."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import json
import wave

from node_runtime.deterrence import siren as siren_module


class RunningProcess:
    def poll(self):
        return None

    def wait(self):
        return 0


def _settings(tmp_path):
    return SimpleNamespace(
        siren_file=str(tmp_path / "speaker" / "warning.wav"),
        speaker_enabled=True,
        siren_enabled=True,
        deterrence_cooldown_sec=30.0,
        speaker_device="default",
        deterrence_frequency_min_hz=900.0,
        deterrence_frequency_max_hz=1100.0,
        deterrence_duration_sec=0.08,
        deterrence_output_amplitude=0.08,
        deterrence_state_file=str(tmp_path / "state" / "deterrence.json"),
    )


def _mock_hardware(monkeypatch):
    monkeypatch.setattr(siren_module.shutil, "which", lambda _: "/usr/bin/aplay")
    monkeypatch.setattr(
        siren_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout="card 0: USB [USB Audio], device 0: USB Audio [USB Audio]\n", stderr=""
        ),
    )
    monkeypatch.setattr(siren_module.subprocess, "Popen", lambda *args, **kwargs: RunningProcess())


def test_warning_uses_new_random_pitch_within_bounded_band(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    monkeypatch.setattr(siren_module, "get_settings", lambda: settings)
    _mock_hardware(monkeypatch)
    # Deterministically drive distinct values through the secure random API.
    values = iter([12, 187])
    monkeypatch.setattr(siren_module.secrets, "randbelow", lambda _span: next(values))

    controller = siren_module.DeterrenceController(enabled=True)
    first = controller.trigger(["person"])
    assert first.started is True
    assert first.frequency_hz == 912.0
    assert 900 <= first.frequency_hz <= 1100
    assert first.duration_sec == 0.08

    # Simulate the next eligible warning after the mandatory cooldown.
    controller.last_trigger_time -= 31
    second = controller.trigger(["dog"])
    assert second.started is True
    assert second.frequency_hz == 1087.0
    assert second.frequency_hz != first.frequency_hz
    assert second.emission_count == 2

    with wave.open(settings.siren_file, "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getframerate() == 22050
        assert audio.getnframes() > 0
    state = json.loads(Path(settings.deterrence_state_file).read_text())
    assert state["emission_count"] == 2
    assert state["last_trigger_time_epoch"] > 0
    # A process restart must retain the cooldown rather than resetting it.
    restarted = siren_module.DeterrenceController(enabled=True)
    blocked = restarted.trigger(["person"])
    assert blocked.started is False
    assert blocked.reason.startswith("cooldown_")


def test_output_probe_fails_closed_without_playback_card(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    monkeypatch.setattr(siren_module, "get_settings", lambda: settings)
    monkeypatch.setattr(siren_module.shutil, "which", lambda _: "/usr/bin/aplay")
    monkeypatch.setattr(siren_module.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="No soundcards found.\n", stderr=""))
    popen = Mock()
    monkeypatch.setattr(siren_module.subprocess, "Popen", popen)

    controller = siren_module.DeterrenceController(enabled=True)
    result = controller.trigger(["person"])
    assert result.started is False
    assert result.reason == "no_alsa_playback_card"
    popen.assert_not_called()


def test_speaker_disabled_never_claims_playback(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    monkeypatch.setattr(siren_module, "get_settings", lambda: settings)
    popen = Mock()
    monkeypatch.setattr(siren_module.subprocess, "Popen", popen)
    controller = siren_module.DeterrenceController(enabled=False)
    result = controller.trigger(["dog"])
    assert result.started is False
    assert result.reason == "speaker_disabled"
    popen.assert_not_called()


def test_default_output_policy_fails_closed_until_commissioned(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    settings.speaker_enabled = False
    settings.siren_enabled = False
    monkeypatch.setattr(siren_module, "get_settings", lambda: settings)
    popen = Mock()
    monkeypatch.setattr(siren_module.subprocess, "Popen", popen)

    controller = siren_module.DeterrenceController()
    result = controller.trigger(["person"])
    assert result.started is False
    assert result.reason == "speaker_disabled"
    popen.assert_not_called()


def test_telegram_reports_only_real_playback_and_exact_pitch(tmp_path, monkeypatch):
    from node_runtime.monitoring import telegram_lifecycle as telegram_module

    settings = _settings(tmp_path)
    settings.node_id = "test-node"
    settings.telegram_queue_path = str(tmp_path / "telegram.db")
    sent = []
    monkeypatch.setattr(telegram_module, "get_settings", lambda: settings)
    monkeypatch.setattr(telegram_module, "send_message", lambda text, chat_id=None: sent.append(text) or True)
    notifier = telegram_module.TelegramLifecycleNotifier(db_path=str(tmp_path / "telegram.db"))

    notifier.notify_deterrence(["person"], SimpleNamespace(started=False), "evt-no-playback")
    assert sent == []

    result = SimpleNamespace(
        started=True, emission_count=4, frequency_hz=987.0,
        frequency_min_hz=900.0, frequency_max_hz=1100.0, duration_sec=1.5,
    )
    notifier.notify_deterrence(["dog"], result, "evt-4")
    assert len(sent) == 1
    for expected in ("dog", "Emission: #4", "987 Hz (randomly selected)", "Duration: 1.50s", "Playback: Started", "evt-4"):
        assert expected in sent[0]
