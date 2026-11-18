"""AWARESPAN local speaker warning with bounded randomisation and hardware gates."""

import json
import math
import os
import re
import secrets
import shutil
import struct
import subprocess
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from shared.config.settings import get_settings
from shared.logging.logger import get_logger

log = get_logger("node_runtime.deterrence")


@dataclass
class DeterrenceResult:
    started: bool
    reason: str
    emission_count: int
    frequency_min_hz: float
    frequency_max_hz: float
    duration_sec: float
    amplitude: float
    speaker_device: str
    frequency_hz: Optional[float] = None
    started_at_ms: int = 0


def _resolve_writable_path(preferred: Path, fallback: Path) -> Path:
    """Use preferred path if its parent can be created and written; otherwise fall back."""
    try:
        preferred.parent.mkdir(parents=True, exist_ok=True)
        if os.access(preferred.parent, os.W_OK):
            return preferred
    except OSError:
        pass
    try:
        fallback.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return fallback


def _find_exact_binary(name: str) -> Optional[str]:
    """Return path from shutil.which only if the resolved binary matches name."""
    resolved = shutil.which(name)
    if resolved and Path(resolved).name == name:
        return resolved
    return None


class DeterrenceController:
    """Play a brief, audible warning through an ALSA, PipeWire, or PulseAudio playback device.

    A fresh, cryptographically selected pitch is generated for each emission
    within the configured 900–1100 Hz audible alert range. This is a generic
    warning tone, not a research-validated human or animal deterrent. The range
    is not claimed to prevent habituation. Digital amplitude is not acoustic SPL;
    keep output disabled until the installed speaker has been measured and calibrated.
    """

    ALERT_MIN_HZ = 900.0
    ALERT_MAX_HZ = 1100.0
    MAX_DURATION_SEC = 1.5
    MAX_AMPLITUDE = 0.08

    def __init__(
        self,
        siren_file: Optional[str] = None,
        enabled: Optional[bool] = None,
        cooldown_sec: Optional[float] = None,
        speaker_device: Optional[str] = None,
        frequency_min_hz: Optional[float] = None,
        frequency_max_hz: Optional[float] = None,
        duration_sec: Optional[float] = None,
        amplitude: Optional[float] = None,
    ):
        settings = get_settings()
        local_state_root = Path(getattr(settings, "repo_root", Path.cwd())) / "state"
        self.siren_file = _resolve_writable_path(
            Path(siren_file or settings.siren_file),
            local_state_root / "audio" / "presence_warning.wav",
        )
        self.enabled = bool(settings.siren_enabled and settings.speaker_enabled) if enabled is None else enabled
        self.cooldown_sec = float(cooldown_sec if cooldown_sec is not None else settings.deterrence_cooldown_sec)
        self.speaker_device = speaker_device or settings.speaker_device
        self.frequency_min_hz = float(frequency_min_hz if frequency_min_hz is not None else settings.deterrence_frequency_min_hz)
        self.frequency_max_hz = float(frequency_max_hz if frequency_max_hz is not None else settings.deterrence_frequency_max_hz)
        self.duration_sec = float(duration_sec if duration_sec is not None else settings.deterrence_duration_sec)
        self.amplitude = float(amplitude if amplitude is not None else settings.deterrence_output_amplitude)
        if not (self.ALERT_MIN_HZ <= self.frequency_min_hz <= self.frequency_max_hz <= self.ALERT_MAX_HZ):
            raise ValueError("Alert pitch must remain within the configured 900–1100 Hz audible range")
        if not (0.0 < self.duration_sec <= self.MAX_DURATION_SEC):
            raise ValueError("Speaker warning duration must be between 0 and 1.5 seconds")
        if not (0.0 < self.amplitude <= self.MAX_AMPLITUDE):
            raise ValueError("Speaker digital amplitude must be greater than 0 and at most 0.08")
        if self.cooldown_sec < 30.0:
            raise ValueError("Speaker warning cooldown must be at least 30 seconds")

        self.last_trigger_time = 0.0
        self.muted = False
        self.state_file = _resolve_writable_path(
            Path(settings.deterrence_state_file),
            local_state_root / "deterrence_state.json",
        )
        self._state_lock = threading.Lock()
        self._hardware_lock = threading.Lock()
        self._hardware_checked_at = 0.0
        self._hardware_status: Dict[str, object] = {
            "available": False,
            "device": self.speaker_device,
            "cards": [],
            "backend": "none",
            "reason": "not_checked",
        }
        self.emission_count, self.last_trigger_time = self._load_state()
        self.last_frequency_hz: Optional[float] = None
        self.last_result = self._result(False, "not_started")

    def _probe_desktop_audio_sinks(self) -> Optional[Dict[str, object]]:
        """Probe PipeWire or PulseAudio playback sinks on desktop Linux hosts (e.g. Fedora)."""
        pw_play = _find_exact_binary("pw-play")
        paplay = _find_exact_binary("paplay")
        if not pw_play and not paplay:
            return None

        sinks: List[str] = []
        pactl = _find_exact_binary("pactl")
        if pactl:
            try:
                probe = subprocess.run([pactl, "list", "short", "sinks"], capture_output=True, text=True, timeout=3, check=False)
                if probe.returncode == 0:
                    sinks = [line.strip() for line in (probe.stdout or "").splitlines() if line.strip()]
            except Exception:
                pass

        if not sinks:
            wpctl = _find_exact_binary("wpctl")
            if wpctl:
                try:
                    probe = subprocess.run([wpctl, "status"], capture_output=True, text=True, timeout=3, check=False)
                    if probe.returncode == 0 and "Sinks:" in (probe.stdout or ""):
                        in_sinks = False
                        for line in probe.stdout.splitlines():
                            if "Sinks:" in line:
                                in_sinks = True
                                continue
                            if in_sinks:
                                stripped = line.strip()
                                if any(k in stripped for k in ("Sources:", "Filters:", "Streams:", "Video", "Settings")):
                                    break
                                if re.search(r"\d+\.\s+\S+", stripped):
                                    sinks.append(stripped)
                except Exception:
                    pass

        if not sinks:
            return None

        if pw_play:
            return {
                "available": True,
                "device": self.speaker_device,
                "cards": sinks,
                "backend": "pipewire",
                "reason": "pipewire_sink_detected",
            }
        return {
            "available": True,
            "device": self.speaker_device,
            "cards": sinks,
            "backend": "pulseaudio",
            "reason": "pulseaudio_sink_detected",
        }

    def hardware_status(self, refresh: bool = False) -> Dict[str, object]:
        """Return playback-card availability (not proof a transducer is attached)."""
        with self._hardware_lock:
            now = time.monotonic()
            if not refresh and now - self._hardware_checked_at < 5.0:
                return dict(self._hardware_status)
            self._hardware_checked_at = now
            player = shutil.which("aplay")
            if player:
                try:
                    probe = subprocess.run([player, "-l"], capture_output=True, text=True, timeout=3, check=False)
                    cards = [line.strip() for line in (probe.stdout or "").splitlines() if re.match(r"^\s*card\s+\d+:", line)]
                    if probe.returncode == 0 and bool(cards):
                        self._hardware_status = {
                            "available": True,
                            "device": self.speaker_device,
                            "cards": cards,
                            "backend": "alsa",
                            "reason": "alsa_playback_card_detected",
                        }
                        return dict(self._hardware_status)
                except Exception as exc:
                    desktop = self._probe_desktop_audio_sinks()
                    if desktop:
                        self._hardware_status = desktop
                        return dict(self._hardware_status)
                    self._hardware_status = {
                        "available": False,
                        "device": self.speaker_device,
                        "cards": [],
                        "backend": "none",
                        "reason": f"hardware_probe_failed:{type(exc).__name__}",
                    }
                    return dict(self._hardware_status)

                desktop = self._probe_desktop_audio_sinks()
                if desktop:
                    self._hardware_status = desktop
                    return dict(self._hardware_status)

                self._hardware_status = {
                    "available": False,
                    "device": self.speaker_device,
                    "cards": [],
                    "backend": "none",
                    "reason": "no_alsa_playback_card",
                }
                return dict(self._hardware_status)

            desktop = self._probe_desktop_audio_sinks()
            if desktop:
                self._hardware_status = desktop
                return dict(self._hardware_status)

            self._hardware_status = {
                "available": False,
                "device": self.speaker_device,
                "cards": [],
                "backend": "none",
                "reason": "aplay_not_installed",
            }
            return dict(self._hardware_status)

    def _load_state(self) -> tuple[int, float]:
        """Load persistent count and last emission time to preserve cooldown on restart."""
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            emission_count = max(0, int(data.get("emission_count", 0)))
            last_trigger_time = max(0.0, float(data.get("last_trigger_time_epoch", 0.0)))
            return emission_count, last_trigger_time
        except FileNotFoundError:
            return 0, 0.0
        except Exception as exc:
            log.warning("Could not read deterrence state: %s", exc)
            return 0, 0.0

    def _persist_emission_count(self) -> None:
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.state_file.with_suffix(self.state_file.suffix + ".tmp")
            payload = {
                "emission_count": self.emission_count,
                "last_trigger_time_epoch": self.last_trigger_time,
                "updated_at_ms": int(time.time() * 1000),
            }
            temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            os.chmod(temporary, 0o640)
            temporary.replace(self.state_file)
        except Exception as exc:
            log.warning("Could not persist deterrence state: %s", exc)

    def mute(self) -> None:
        self.muted = True
        log.info("Speaker deterrence muted by operator")

    def unmute(self) -> None:
        self.muted = False
        log.info("Speaker deterrence unmuted by operator")

    def _generate_warning_asset(self) -> bool:
        """Create a short local WAV using a fresh random pitch on every call."""
        try:
            self.siren_file.parent.mkdir(parents=True, exist_ok=True)
            sample_rate = 22050
            frame_count = max(1, int(sample_rate * self.duration_sec))
            span = int(round(self.frequency_max_hz - self.frequency_min_hz))
            frequency_hz = self.frequency_min_hz + secrets.randbelow(span + 1)
            self.last_frequency_hz = float(frequency_hz)
            attack_frames = max(1, int(sample_rate * 0.04))
            release_frames = max(1, int(sample_rate * 0.08))
            with wave.open(str(self.siren_file), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                samples = bytearray()
                for index in range(frame_count):
                    envelope = min(1.0, index / attack_frames)
                    envelope *= min(1.0, (frame_count - index) / release_frames)
                    sample = int(32767 * self.amplitude * envelope * math.sin(2.0 * math.pi * frequency_hz * index / sample_rate))
                    samples.extend(struct.pack("<h", sample))
                wav_file.writeframesraw(samples)
            os.chmod(self.siren_file, 0o640)
            return True
        except Exception as exc:
            log.error("Could not prepare local speaker warning audio: %s", exc)
            return False

    def trigger(self, labels: List[str]) -> DeterrenceResult:
        now = time.time()
        if not self.enabled:
            return self._result(False, "speaker_disabled")
        if self.muted:
            return self._result(False, "muted")
        hardware = self.hardware_status()
        if not hardware.get("available"):
            return self._result(False, str(hardware.get("reason", "audio_output_unavailable")))
        remaining = self.cooldown_sec - (now - self.last_trigger_time)
        if remaining > 0:
            return self._result(False, f"cooldown_{remaining:.1f}s")
        if not self._generate_warning_asset():
            return self._result(False, "audio_asset_unavailable")
        backend = str(hardware.get("backend") or "alsa")
        commands: List[List[str]] = []
        if backend == "pipewire":
            pw_play = _find_exact_binary("pw-play")
            if pw_play:
                cmd = [pw_play]
                if self.speaker_device and self.speaker_device != "default":
                    cmd.extend(["--target", self.speaker_device])
                cmd.append(str(self.siren_file))
                commands.append(cmd)
        elif backend == "pulseaudio":
            paplay = _find_exact_binary("paplay")
            if paplay:
                cmd = [paplay]
                if self.speaker_device and self.speaker_device != "default":
                    cmd.extend(["--device", self.speaker_device])
                cmd.append(str(self.siren_file))
                commands.append(cmd)
        else:
            player = shutil.which("aplay")
            if player:
                cmd = [player, "-q"]
                if self.speaker_device:
                    cmd.extend(["-D", self.speaker_device])
                cmd.append(str(self.siren_file))
                commands.append(cmd)
            # Desktop Linux (e.g. Fedora PipeWire) fallback if ALSA direct playback fails
            pw_play = _find_exact_binary("pw-play")
            if pw_play:
                commands.append([pw_play, str(self.siren_file)])
            else:
                paplay = _find_exact_binary("paplay")
                if paplay:
                    commands.append([paplay, str(self.siren_file)])

        if not commands:
            return self._result(False, "aplay_not_installed")

        last_failure_reason = "speaker_output_failed"
        started_ok = False
        for command in commands:
            try:
                process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # Reap the short-lived player process without blocking the inference loop.
                threading.Thread(target=process.wait, name="awarespan-audio-reaper", daemon=True).start()
                time.sleep(0.12)
                exit_code = process.poll()
                if exit_code is None or exit_code == 0:
                    started_ok = True
                    break
                last_failure_reason = f"speaker_output_failed_{exit_code}"
            except Exception as exc:
                log.warning("Speaker playback could not be started via %s: %s", command[0], exc)
                last_failure_reason = "speaker_output_failed"

        if not started_ok:
            return self._result(False, last_failure_reason)

        with self._state_lock:
            self.last_trigger_time = now
            self.emission_count += 1
            self._persist_emission_count()
        result = DeterrenceResult(
            started=True,
            reason="playback_started",
            emission_count=self.emission_count,
            frequency_min_hz=self.frequency_min_hz,
            frequency_max_hz=self.frequency_max_hz,
            duration_sec=self.duration_sec,
            amplitude=self.amplitude,
            speaker_device=self.speaker_device,
            frequency_hz=self.last_frequency_hz,
            started_at_ms=int(now * 1000),
        )
        self.last_result = result
        log.info("Pi speaker warning started for %s; emission=%d, selected_frequency=%.0fHz, duration=%.2fs",
                 ", ".join(labels), result.emission_count, result.frequency_hz or 0.0, result.duration_sec)
        return result

    def _result(self, started: bool, reason: str) -> DeterrenceResult:
        result = DeterrenceResult(
            started=started,
            reason=reason,
            emission_count=self.emission_count,
            frequency_min_hz=self.frequency_min_hz,
            frequency_max_hz=self.frequency_max_hz,
            duration_sec=self.duration_sec,
            amplitude=self.amplitude,
            speaker_device=self.speaker_device,
            frequency_hz=None,
        )
        self.last_result = result
        return result

    def trigger_siren(self, labels: List[str]) -> bool:
        """Backward-compatible boolean API; True only if aplay was started."""
        return self.trigger(labels).started

    def trigger_strobe(self, duration_sec: float = 5.0) -> None:
        log.info("Visual strobe requested for %.1fs (no strobe driver configured)", duration_sec)
