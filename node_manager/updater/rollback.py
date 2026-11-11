"""
AWARESPAN — Automatic Rollback Manager
Restores repository to previous stable commit SHA, reinstalls dependencies, and restarts services.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import sys
from pathlib import Path
from typing import Optional

from shared.config.settings import get_settings
from shared.logging.logger import get_logger
from shared.utilities.system import FileLock, get_git_commit, safe_subprocess_run
from node_manager.service_manager import ServiceManager, KNOWN_SERVICES
from node_manager.health_check import HealthChecker
from node_manager.updater.version_state import VersionStateManager

log = get_logger("node_manager.rollback")


class RollbackManager:
    """Manages fast, deterministic rollbacks to the last known working revision."""

    def __init__(self, state_manager: Optional[VersionStateManager] = None):
        self.settings = get_settings()
        self.state_manager = state_manager or VersionStateManager()
        self.services = ServiceManager()
        self.health = HealthChecker()

    def rollback(self, target_commit: Optional[str] = None, reason: str = "Automatic rollback after health check failure") -> bool:
        """
        Roll back repository to target commit, reinstall runtime deps if necessary,
        and restart services.
        """
        lock = FileLock(self.settings.lock_file, timeout_sec=15.0)
        with lock:
            state = self.state_manager.get_state()
            target = target_commit or state.rollback_target

            if not target or target == "unknown":
                log.error("No valid rollback target available in state or arguments.")
                return False

            current = get_git_commit(cwd=str(self.settings.repo_root))
            if current == target:
                log.info("Already at target commit %s; nothing to roll back.", target[:8])
                return True

            log.warning("Initiating rollback: %s -> %s. Reason: %s", current[:8], target[:8], reason)

            # 1. Reset Git working tree
            code, stdout, stderr = safe_subprocess_run(
                ["git", "reset", "--hard", target],
                timeout=30,
                cwd=str(self.settings.repo_root),
            )
            if code != 0:
                log.error("git reset --hard failed: %s", stderr)
                return False

            # 2. Re-install runtime requirements if requirements file exists
            req_file = self.settings.repo_root / "requirements" / "runtime.txt"
            if req_file.exists():
                safe_subprocess_run(
                    [sys.executable, "-m", "pip", "install", "--no-warn-script-location", "-r", str(req_file)],
                    timeout=180,
                    cwd=str(self.settings.repo_root),
                )

            # 3. Reload systemd daemon
            if self.services.is_available:
                self.services.daemon_reload()

            # 4. Restart runtime and power monitor services
            self.services.restart(KNOWN_SERVICES["node"])
            self.services.restart(KNOWN_SERVICES["power_monitor"])

            # 5. Verify post-rollback health
            report = self.health.verify_node_health(max_wait_sec=20.0, poll_interval_sec=2.0)
            log.info("Post-rollback health check: %s (%s)", report.overall_healthy, report.message)

            # 6. Record state
            self.state_manager.record_rollback(target, reason)

            # 7. Send Telegram alert if token available
            self._notify_telegram(target, reason, report.overall_healthy)

            return report.overall_healthy

    def _notify_telegram(self, target_commit: str, reason: str, healthy: bool) -> None:
        """Send emergency rollback notification to Telegram."""
        if not self.settings.bot_token or not self.settings.primary_chat_id:
            return
        status_icon = "✅" if healthy else "❌"
        msg = (
            f"⚠️ <b>AWARESPAN Rollback Notice</b>\n"
            f"Node: <code>{self.settings.node_id}</code>\n"
            f"Target: <code>{target_commit[:8]}</code>\n"
            f"Post-Rollback Health: {status_icon}\n"
            f"Reason: <i>{reason}</i>"
        )
        try:
            import urllib.request
            import json
            url = f"https://api.telegram.org/bot{self.settings.bot_token}/sendMessage"
            payload = json.dumps({
                "chat_id": self.settings.primary_chat_id,
                "text": msg,
                "parse_mode": "HTML",
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
        except Exception as exc:
            log.warning("Failed to send rollback Telegram alert: %s", exc)
