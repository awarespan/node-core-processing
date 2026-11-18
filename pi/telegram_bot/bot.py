"""
AWARESPAN — Interactive Operator Telegram Bot
Provides real-time node diagnostics, remote health checks, and live photo threat inference.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import json
import os
import shutil
import time
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional

import requests
import cv2
import numpy as np

from shared.config.settings import get_settings
from shared.logging.logger import get_logger, sanitize_text
from shared.utilities.system import get_git_commit, get_raspberry_pi_model, get_throttled_state
from node_runtime.detection.visual.detector import VisualDetector
from node_runtime.processing.threat_assessment import ThreatAssessor

log = get_logger("node_runtime.telegram_bot")


class TelegramOperatorBot:
    """Interactive Telegram bot for operator command, telemetry, and visual test inference."""

    def __init__(self):
        self.settings = get_settings()
        self.bot_token = self.settings.bot_token
        self.allowed_chats = set(self.settings.allowed_chat_ids)
        if self.settings.primary_chat_id:
            self.allowed_chats.add(self.settings.primary_chat_id)

        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.cache_dir = self.settings.repo_root / "bot_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.detector: Optional[VisualDetector] = None
        self.assessor = ThreatAssessor()
        self.last_text_time = 0.0

    def _get_detector(self) -> VisualDetector:
        """Lazy load visual detector when first needed."""
        if self.detector is None:
            self.detector = VisualDetector(imgsz=640, confidence=0.25)
        return self.detector

    def send_message(self, chat_id: str, text: str) -> bool:
        """Send HTML text message."""
        try:
            res = requests.post(
                f"{self.api_url}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                timeout=10,
            )
            return res.status_code == 200
        except Exception as exc:
            log.warning("Failed to send telegram message: %s", sanitize_text(str(exc)))
            return False

    def handle_command(self, text: str, chat_id: str) -> None:
        """Handle incoming slash command or prompt."""
        cmd = (text or "").strip().lower()

        if cmd in ("/start", "/help"):
            msg = (
                "🛡️ <b>AWARESPAN Edge Node Bot</b>\n"
                "<i>Awareness Without Boundaries.</i>\n"
                "<b>Official Problem Statement:</b> An AI-Powered Safety Device.\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "<b>Commands:</b>\n"
                "• /status — Node status and power metrics\n"
                "• /threats — Current threat classification policy\n"
                "• /health — Bounded subsystem health checks\n"
                "• /help — Show this information\n\n"
                "📷 <i>Send any photo to trigger live YOLO weapon & threat inference!</i>\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                f"Node: <code>{self.settings.node_id}</code> | Contact: <code>awarespan@bchbenjamin.in</code>"
            )
            self.send_message(chat_id, msg)
            return

        if cmd == "/threats":
            msg = (
                "⚔️ <b>AWARESPAN Threat Policy</b>\n"
                f"<b>Tier 1 (Nuisance/Animals):</b>\n<code>{', '.join(sorted(self.settings.tier1_labels))}</code>\n\n"
                f"<b>Tier 2 (Weapons/Vehicles):</b>\n<code>{', '.join(sorted(self.settings.tier2_labels))}</code>\n\n"
                f"<b>Confidence Threshold:</b> <code>{self.settings.confidence_threshold:.2f}</code>\n"
                f"<b>Siren Enabled:</b> <code>{self.settings.siren_enabled}</code>"
            )
            self.send_message(chat_id, msg)
            return

        if cmd in ("/status", "/health"):
            power = get_throttled_state()
            hw = get_raspberry_pi_model()
            sha = get_git_commit(cwd=str(self.settings.repo_root))
            msg = (
                f"📊 <b>AWARESPAN Node Status</b>\n"
                f"Node ID: <code>{self.settings.node_id}</code>\n"
                f"Hardware: <code>{hw}</code>\n"
                f"Commit: <code>{sha[:8]}</code>\n"
                f"Branch: <code>{self.settings.update_branch}</code>\n"
                f"CPU Temp: <b>{f'{power.temp_c:.1f}°C' if power.temp_c else 'N/A'}</b>\n"
                f"Throttled: <code>{power.throttled_raw}</code>\n"
                f"Undervoltage NOW: {'⚠️ YES' if power.undervoltage_now else 'No (OK)'}\n"
                f"Undervoltage PAST: {'⚠️ YES' if power.undervoltage_occurred else 'No'}\n"
                f"Backend: <code>{self.settings.backend_api_url}</code>"
            )
            self.send_message(chat_id, msg)
            return

        self.send_message(chat_id, "Type /help for available commands or send a photo for threat test inference.")

    def handle_photo(self, photo_list: List[Dict], chat_id: str) -> None:
        """Download uploaded photo, run YOLO inference, and reply with bounding boxes."""
        log.info("Processing photo inspection request from chat %s...", chat_id)
        photo = sorted(photo_list, key=lambda x: x.get("file_size", 0))[-1]
        file_id = photo["file_id"]

        try:
            # 1. Resolve file path
            resp = requests.get(f"{self.api_url}/getFile?file_id={file_id}", timeout=10).json()
            if not resp.get("ok"):
                self.send_message(chat_id, "⚠️ Failed to resolve uploaded photo.")
                return

            file_path = resp["result"]["file_path"]
            download_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
            img_data = requests.get(download_url, timeout=15).content

            in_path = self.cache_dir / f"input_{int(time.time())}.jpg"
            out_path = self.cache_dir / f"output_{int(time.time())}.jpg"
            in_path.write_bytes(img_data)

            # 2. Decode and run inference
            img_np = np.frombuffer(img_data, dtype=np.uint8)
            frame = cv2.imdecode(img_np, cv2.IMREAD_COLOR)

            detector = self._get_detector()
            annotated_frame, detections = detector.infer(frame)
            assessment = self.assessor.evaluate(detections)

            # Save annotated output
            cv2.imwrite(str(out_path), annotated_frame)

            # 3. Build caption
            tier_icon = "🚨" if assessment.tier == "tier2" else ("⚠️" if assessment.tier == "tier1" else "✅")
            caption = (
                f"{tier_icon} <b>AWARESPAN Threat Assessment: {assessment.threat_level}</b>\n"
                f"Tier: <b>{assessment.tier.upper()}</b>\n"
                f"Detected Objects ({len(detections)}): <code>{', '.join([d.label for d in detections]) or 'None'}</code>\n"
                f"Max Confidence: <code>{assessment.max_confidence:.2f}</code>\n"
                f"Action: {'Emergency Alert' if assessment.tier == 'tier2' else ('Siren Deterrence' if assessment.tier == 'tier1' else 'Pass')}"
            )

            # 4. Upload annotated photo
            with open(out_path, "rb") as f:
                requests.post(
                    f"{self.api_url}/sendPhoto",
                    data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
                    files={"photo": f},
                    timeout=20,
                )

            # Cleanup
            try:
                in_path.unlink(missing_ok=True)
                out_path.unlink(missing_ok=True)
            except Exception:
                pass

        except Exception as exc:
            log.error("Error processing photo: %s", exc)
            self.send_message(chat_id, f"⚠️ Inference failed: {sanitize_text(str(exc))}")

    def run(self) -> None:
        """Main polling loop."""
        if not self.bot_token:
            log.warning("BOT_TOKEN is not configured; Telegram operator bot cannot start.")
            return

        log.info("Starting AWARESPAN Telegram Operator Bot for node %s...", self.settings.node_id)
        offset = None

        while True:
            try:
                url = f"{self.api_url}/getUpdates?timeout=30"
                if offset:
                    url += f"&offset={offset}"

                resp = requests.get(url, timeout=40)
                data = resp.json()

                if data.get("ok"):
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        msg = update.get("message")
                        if not msg:
                            continue

                        chat_id = str(msg["chat"]["id"])
                        if self.allowed_chats and chat_id not in self.allowed_chats:
                            log.warning("Suppressed unauthorized message from chat %s", chat_id)
                            continue

                        if "text" in msg:
                            self.handle_command(msg["text"], chat_id)
                        elif "photo" in msg:
                            self.handle_photo(msg["photo"], chat_id)

                time.sleep(1)

            except Exception as exc:
                log.warning("Telegram polling error: %s", sanitize_text(str(exc)))
                time.sleep(5)


def main():
    bot = TelegramOperatorBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        log.info("Telegram operator bot stopped by operator.")


if __name__ == "__main__":
    main()
