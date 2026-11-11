"""
AWARESPAN — Deterrence Controller
Audio deterrence playback (aplay), strobe/LED triggers, and safety interlocks.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import os
import subprocess
import time
from typing import List, Optional

from shared.config.settings import get_settings
from shared.logging.logger import get_logger

log = get_logger("node_runtime.deterrence")


class DeterrenceController:
    """Manages audio sirens and visual strobes with safety interlocks."""

    def __init__(
        self,
        siren_file: Optional[str] = None,
        enabled: Optional[bool] = None,
        cooldown_sec: float = 8.0,
    ):
        settings = get_settings()
        self.siren_file = siren_file or settings.siren_file
        self.enabled = enabled if enabled is not None else settings.siren_enabled
        self.cooldown_sec = cooldown_sec
        self.last_trigger_time = 0.0
        self.muted = False

    def mute(self) -> None:
        """Emergency mute override."""
        self.muted = True
        log.info("Deterrence controller muted via operator command.")

    def unmute(self) -> None:
        """Unmute deterrence."""
        self.muted = False
        log.info("Deterrence controller unmuted.")

    def trigger_siren(self, labels: List[str]) -> bool:
        """
        Trigger audio siren playback with cooldown check.
        Returns True if siren was triggered, False if suppressed.
        """
        if not self.enabled:
            log.info("Siren disabled in settings; suppressing playback for: %s", ", ".join(labels))
            return False

        if self.muted:
            log.info("Siren muted; suppressing playback for: %s", ", ".join(labels))
            return False

        now = time.time()
        if (now - self.last_trigger_time) < self.cooldown_sec:
            log.info("Siren cooldown active (%.1fs remaining); skipping.", self.cooldown_sec - (now - self.last_trigger_time))
            return False

        self.last_trigger_time = now

        if self.siren_file and os.path.exists(self.siren_file):
            log.info("Deterrence siren playback started for threats: %s", ", ".join(labels))
            try:
                # Run aplay non-blocking or with timeout
                subprocess.Popen(
                    ["aplay", "-q", self.siren_file],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
            except Exception as exc:
                log.warning("aplay execution failed (audio device unavailable): %s", exc)
                return False
        else:
            log.info("Deterrence simulated (siren file not found at %s) for %s", self.siren_file, ", ".join(labels))
            return True

    def trigger_strobe(self, duration_sec: float = 5.0) -> None:
        """Trigger visual strobe light warning."""
        log.info("Visual strobe triggered for %.1fs", duration_sec)
