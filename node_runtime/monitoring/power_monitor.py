"""
AWARESPAN — Power & Thermal Monitor
Monitors Raspberry Pi 5 throttled state, undervoltage, and CPU thermals. Sends Telegram alerts.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import os
import sys
import time
from datetime import datetime
from typing import Optional
import urllib.request
import json
import psutil

from shared.config.settings import get_settings
from shared.logging.logger import get_logger, sanitize_text
from shared.utilities.system import get_throttled_state, get_raspberry_pi_model

log = get_logger("node_runtime.power_monitor")

ALERT_COOLDOWN_SEC = 600  # 10 minutes between repeated alerts


class PowerMonitor:
    """Continuously monitors Pi 5 hardware power, voltage, and thermals."""

    def __init__(self, poll_interval_sec: float = 15.0):
        self.settings = get_settings()
        self.poll_interval = poll_interval_sec
        self.last_undervoltage_alert = 0.0
        self.last_thermal_alert = 0.0

    def send_telegram_alert(self, text: str) -> bool:
        """Send urgent hardware alert via Telegram."""
        if not self.settings.bot_token or not self.settings.primary_chat_id:
            return False

        try:
            url = f"https://api.telegram.org/bot{self.settings.bot_token}/sendMessage"
            payload = json.dumps({
                "chat_id": self.settings.primary_chat_id,
                "text": text,
                "parse_mode": "HTML",
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                return resp.status == 200
        except Exception as exc:
            log.warning("Failed to send Telegram power alert: %s", sanitize_text(str(exc)))
            return False

    def run(self) -> None:
        """Main monitoring loop."""
        log.info("Starting AWARESPAN Power & Thermal Monitor on %s...", get_raspberry_pi_model())

        while True:
            try:
                power = get_throttled_state()
                now = time.time()

                # Undervoltage check
                if power.undervoltage_now:
                    log.warning("CRITICAL: Under-voltage actively detected! (throttled=%s)", power.throttled_raw)
                    if (now - self.last_undervoltage_alert) > ALERT_COOLDOWN_SEC:
                        msg = (
                            f"⚠️ <b>AWARESPAN HARDWARE ALERT</b>\n"
                            f"Node: <code>{self.settings.node_id}</code>\n"
                            f"Issue: <b>Under-voltage Detected NOW</b>\n"
                            f"Throttled State: <code>{power.throttled_raw}</code>\n"
                            f"Temp: {f'{power.temp_c:.1f}°C' if power.temp_c else 'N/A'}\n"
                            f"Action: Verify 27W USB-C PD power supply."
                        )
                        if self.send_telegram_alert(msg):
                            self.last_undervoltage_alert = now

                # Thermal check (> 80°C)
                if power.temp_c and power.temp_c >= 80.0:
                    log.warning("HIGH TEMPERATURE: CPU temp at %.1f°C", power.temp_c)
                    if (now - self.last_thermal_alert) > ALERT_COOLDOWN_SEC:
                        msg = (
                            f"🌡️ <b>AWARESPAN THERMAL WARNING</b>\n"
                            f"Node: <code>{self.settings.node_id}</code>\n"
                            f"CPU Temperature: <b>{power.temp_c:.1f}°C</b>\n"
                            f"Action: Verify heatsink fan and ventilation."
                        )
                        if self.send_telegram_alert(msg):
                            self.last_thermal_alert = now

            except Exception as exc:
                log.error("Error in power monitor loop: %s", exc)

            time.sleep(self.poll_interval)


def main():
    monitor = PowerMonitor()
    try:
        monitor.run()
    except KeyboardInterrupt:
        log.info("Power monitor stopped by operator.")


if __name__ == "__main__":
    main()
