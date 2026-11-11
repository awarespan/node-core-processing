"""
AWARESPAN — Telegram Notification Utility
CLI helper for dispatching formatted alerts, status reports, and operational notifications.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import json
import sys
import urllib.request
from typing import Optional

from shared.config.settings import get_settings
from shared.logging.logger import get_logger, sanitize_text

log = get_logger("node_runtime.telegram_notify")


def send_message(text: str, chat_id: Optional[str] = None) -> bool:
    """Send HTML message via Telegram Bot API with token redaction."""
    settings = get_settings()
    token = settings.bot_token
    target_chat = chat_id or settings.primary_chat_id

    if not token or not target_chat:
        log.warning("Telegram bot token or chat ID not configured; skipping notification.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": target_chat,
        "text": text,
        "parse_mode": "HTML",
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as exc:
        log.error("Failed to deliver Telegram notification: %s", sanitize_text(str(exc)))
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: telegram_notify.py <command> [args...]")
        print("Commands: start, progress, complete, error, custom, alert")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    settings = get_settings()
    node = settings.node_id

    if cmd == "start":
        name = sys.argv[2] if len(sys.argv) > 2 else "Pipeline Job"
        epochs = sys.argv[3] if len(sys.argv) > 3 else "N/A"
        text = f"🚀 <b>AWARESPAN Job Started</b>\nNode: <code>{node}</code>\nTask: <b>{name}</b>\nEpochs: {epochs}"
    elif cmd == "progress":
        ep = sys.argv[2] if len(sys.argv) > 2 else "0"
        tot = sys.argv[3] if len(sys.argv) > 3 else "0"
        loss = sys.argv[4] if len(sys.argv) > 4 else "0.0"
        mAP = sys.argv[5] if len(sys.argv) > 5 else "0.0"
        text = f"📊 <b>AWARESPAN Progress</b>\nNode: <code>{node}</code>\nEpoch: {ep}/{tot}\nLoss: {loss}\nmAP50: {mAP}"
    elif cmd == "complete":
        artifact = sys.argv[2] if len(sys.argv) > 2 else "Done"
        text = f"✅ <b>AWARESPAN Job Completed</b>\nNode: <code>{node}</code>\nOutput: <code>{artifact}</code>"
    elif cmd == "error":
        err = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "Unknown error"
        text = f"❌ <b>AWARESPAN Alert</b>\nNode: <code>{node}</code>\nError: <code>{err}</code>"
    elif cmd == "alert":
        msg = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "Alert"
        text = f"🚨 <b>AWARESPAN Alert</b>\nNode: <code>{node}</code>\n{msg}"
    else:
        text = " ".join(sys.argv[1:])

    success = send_message(text)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
