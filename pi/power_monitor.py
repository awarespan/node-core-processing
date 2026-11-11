#!/usr/bin/env python3
"""
SIP Power Monitor — monitors Raspberry Pi undervoltage and sends Telegram alerts.
Independent of training/inference. Runs as a systemd service.

Behavior:
- Polls ~vcgencmd get_throttled~ once per minute.
- Tracks current undervoltage state persistently.
- Sends ONE Telegram alert after >30 minutes of continuous undervoltage.
- Sends ONE recovery notification after the condition clears.
- Never spams: tracks alert-sent state across restarts.
"""

import os
import sys
import json
import time
import signal
import subprocess
from datetime import datetime
from pathlib import Path

HOME = os.path.expanduser("~")
STATE_FILE = os.path.join(HOME, "edge-ai", "state", "power_monitor.json")
ALERT_THRESHOLD_MINUTES = 30
POLL_INTERVAL_SECONDS = 60

# Add edge-ai to path for telegram_notify
sys.path.insert(0, os.path.join(HOME, "edge-ai"))

# ── State management ──────────────────────────────────────────────────────────

def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return _default_state()


def _default_state() -> dict:
    return {
        "first_undervoltage_time": None,
        "last_undervoltage_time": None,
        "last_healthy_time": None,
        "last_probe_result": None,
        "last_probe_raw": None,
        "probe_error": None,
        "alert_sent": False,
        "recovery_sent": False,
        "consecutive_healthy": 0,
        "gap_minutes": 0,
    }


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)


# ── Hardware probing ──────────────────────────────────────────────────────────

def get_power_status() -> tuple:
    """
    Query vcgencmd get_throttled for current undervoltage status.

    Returns (is_currently_undervolted: bool, raw_output: str, error: str|None)
    Bit flags from get_throttled:
      bit 0 (0x1): under-voltage now
      bit 1 (0x2): under-voltage historically (throttled at some point)
      bit 2 (0x4): arm frequency capped now
      bit 3 (0x8): arm frequency historically capped
      bit 4 (0x10): soft temperature limit now
      bit 5 (0x20): soft temperature historically limited
      bit 6 (0x40): throttled now
      bit 7 (0x80): throttled historically

    We only care about bit 0 (current undervoltage).
    """
    try:
        result = subprocess.run(
            ["vcgencmd", "get_throttled"],
            capture_output=True, text=True, timeout=10
        )
        raw = result.stdout.strip()
        if result.returncode != 0:
            return False, raw, f"vcgencmd returned {result.returncode}"

        # Parse: "throttled=0x50000"
        if "=" not in raw:
            return False, raw, f"Unexpected format: {raw}"

        hex_val = int(raw.split("=")[1], 16)
        is_undervolted = bool(hex_val & 0x1)  # Bit 0 = current undervoltage
        return is_undervolted, raw, None

    except FileNotFoundError:
        return False, "", "vcgencmd not found (not running on Pi?)"
    except subprocess.TimeoutExpired:
        return False, "", "vcgencmd timed out"
    except Exception as e:
        return False, "", str(e)


# ── Telegram alerts ───────────────────────────────────────────────────────────

def send_telegram(message: str) -> bool:
    """Send a Telegram alert via the existing bot."""
    try:
        from telegram_notify import send_telegram as tg_send
        result = tg_send(message)
        return result is not None
    except Exception as e:
        log(f"Telegram send failed: {e}")
        return False


def send_alert(state: dict, start_time: str, duration_minutes: float, raw: str) -> None:
    node_name = os.getenv("PI_NODE_ID", "sip-pi-001")
    msg = (
        f"⚠️ <b>LOW POWER ALERT — {node_name}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔋 Current undervoltage detected for\n"
        f"   <b>{duration_minutes:.0f} minutes</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 Started: {start_time}\n"
        f"💡 Check: power adapter, cable, and USB connections.\n"
        f"📊 Status raw: <code>{raw}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Auto-monitor — SIP Power Monitor</i>"
    )
    send_telegram(msg)


def send_recovery(state: dict, last_healthy: str) -> None:
    node_name = os.getenv("PI_NODE_ID", "sip-pi-001")
    msg = (
        f"✅ <b>Power Restored — {node_name}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔋 Undervoltage condition cleared.\n"
        f"🕐 Last healthy: {last_healthy}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Auto-monitor — SIP Power Monitor</i>"
    )
    send_telegram(msg)


# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[power-monitor] {ts} {msg}", flush=True)


# ── Main loop ─────────────────────────────────────────────────────────────────

def run():
    log(f"Starting SIP Power Monitor")
    log(f"Poll interval: {POLL_INTERVAL_SECONDS}s, Alert threshold: {ALERT_THRESHOLD_MINUTES}min")

    # Handle SIGTERM gracefully
    def handle_sigterm(signum, frame):
        log("Received SIGTERM, exiting.")
        sys.exit(0)
    signal.signal(signal.SIGTERM, handle_sigterm)

    while True:
        state = load_state()
        is_undervolted, raw, error = get_power_status()
        now = datetime.now().isoformat()

        state["last_probe_result"] = "undervolted" if is_undervolted else "healthy"
        state["last_probe_raw"] = raw
        state["probe_error"] = error

        if error:
            log(f"Probe error: {error}")
            # Don't false-alert on monitoring gap
            save_state(state)
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        if is_undervolted:
            state["last_undervoltage_time"] = now
            state["consecutive_healthy"] = 0

            if state["first_undervoltage_time"] is None:
                state["first_undervoltage_time"] = now
                log(f"Undervoltage detected. Monitoring started at {now}")

            # Calculate duration
            first_ts = datetime.fromisoformat(state["first_undervoltage_time"])
            duration_minutes = (datetime.now() - first_ts).total_seconds() / 60

            if not state["alert_sent"] and duration_minutes > ALERT_THRESHOLD_MINUTES:
                log(f"⚠️  Undervoltage >30min! Sending alert.")
                send_alert(state, state["first_undervoltage_time"], duration_minutes, raw)
                state["alert_sent"] = True

        else:
            state["last_healthy_time"] = now

            if state["first_undervoltage_time"] is not None:
                state["consecutive_healthy"] += 1
                # Require 3 consecutive healthy samples before declaring recovery
                if state["consecutive_healthy"] >= 3:
                    if state["alert_sent"] and not state["recovery_sent"]:
                        log("Recovery detected. Sending notification.")
                        send_recovery(state, now)
                        state["recovery_sent"] = True
                    elif not state["alert_sent"]:
                        # Brief undervoltage that didn't reach threshold
                        log("Undervoltage cleared before threshold.")
                        state["first_undervoltage_time"] = None
                        state["last_undervoltage_time"] = None

            # If already recovered and stable, reset for next potential episode
            if state["recovery_sent"] and state["consecutive_healthy"] >= 5:
                log("Resetting for next episode.")
                state["first_undervoltage_time"] = None
                state["last_undervoltage_time"] = None
                state["alert_sent"] = False
                state["recovery_sent"] = False
                state["consecutive_healthy"] = 0

        save_state(state)

        status = "⚡ undervolted" if is_undervolted else "✅ healthy"
        if is_undervolted and state["first_undervoltage_time"]:
            first_ts = datetime.fromisoformat(state["first_undervoltage_time"])
            dur = (datetime.now() - first_ts).total_seconds() / 60
            status += f" ({dur:.0f}min)"
        log(f"Status: {status}")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()