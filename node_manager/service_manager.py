"""
AWARESPAN — Systemd Service Manager
Abstraction over systemctl for starting, stopping, restarting, and checking service health.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import os
import shutil
from typing import Dict, List, Optional, Set

from shared.logging.logger import get_logger
from shared.utilities.system import safe_subprocess_run

log = get_logger("node_manager.service_manager")

KNOWN_SERVICES = {
    "node": "awarespan-node.service",
    "power_monitor": "awarespan-power-monitor.service",
    "updater": "awarespan-updater.service",
    "updater_timer": "awarespan-updater.timer",
    "training": "awarespan-training.service",
    "bot": "awarespan-bot.service",
}


class ServiceManager:
    """Controls AWARESPAN systemd services."""

    def __init__(self):
        self._has_systemctl = shutil.which("systemctl") is not None and os.path.exists("/run/systemd/system")

    @property
    def is_available(self) -> bool:
        """Check if systemd management is available on this host."""
        return self._has_systemctl

    def is_active(self, service_name: str) -> bool:
        """Check if a systemd unit is currently active (running)."""
        if not self._has_systemctl:
            return False
        code, stdout, _ = safe_subprocess_run(
            ["systemctl", "is-active", "--quiet", service_name],
            timeout=5,
        )
        return code == 0

    def is_enabled(self, service_name: str) -> bool:
        """Check if a systemd unit is enabled for auto-start."""
        if not self._has_systemctl:
            return False
        code, _, _ = safe_subprocess_run(
            ["systemctl", "is-enabled", "--quiet", service_name],
            timeout=5,
        )
        return code == 0

    def start(self, service_name: str) -> bool:
        """Start a systemd unit."""
        if not self._has_systemctl:
            log.warning("systemd not available; cannot start %s", service_name)
            return False
        code, _, stderr = safe_subprocess_run(
            ["sudo", "systemctl", "start", service_name],
            timeout=30,
        )
        if code != 0:
            log.error("Failed to start %s: %s", service_name, stderr)
            return False
        log.info("Started service %s", service_name)
        return True

    def stop(self, service_name: str) -> bool:
        """Stop a systemd unit."""
        if not self._has_systemctl:
            log.warning("systemd not available; cannot stop %s", service_name)
            return False
        code, _, stderr = safe_subprocess_run(
            ["sudo", "systemctl", "stop", service_name],
            timeout=30,
        )
        if code != 0:
            log.error("Failed to stop %s: %s", service_name, stderr)
            return False
        log.info("Stopped service %s", service_name)
        return True

    def restart(self, service_name: str) -> bool:
        """Restart a systemd unit."""
        if not self._has_systemctl:
            log.warning("systemd not available; cannot restart %s", service_name)
            return False
        code, _, stderr = safe_subprocess_run(
            ["sudo", "systemctl", "restart", service_name],
            timeout=45,
        )
        if code != 0:
            log.error("Failed to restart %s: %s", service_name, stderr)
            return False
        log.info("Restarted service %s", service_name)
        return True

    def daemon_reload(self) -> bool:
        """Reload systemd manager configuration."""
        if not self._has_systemctl:
            return False
        code, _, stderr = safe_subprocess_run(
            ["sudo", "systemctl", "daemon-reload"],
            timeout=15,
        )
        if code != 0:
            log.error("systemctl daemon-reload failed: %s", stderr)
            return False
        log.info("systemctl daemon-reload succeeded")
        return True

    def get_all_statuses(self) -> Dict[str, Dict[str, bool]]:
        """Return active and enabled states for all known AWARESPAN units."""
        result = {}
        for key, unit in KNOWN_SERVICES.items():
            result[key] = {
                "unit": unit,
                "active": self.is_active(unit),
                "enabled": self.is_enabled(unit),
            }
        return result

    def determine_affected_services(self, changed_files: List[str]) -> Set[str]:
        """
        Analyze the list of changed file paths to determine which services require restarting.
        Minimizes unnecessary service interruptions.
        """
        affected = set()

        for f in changed_files:
            f_norm = f.replace("\\", "/").strip()

            # Shared code changes affect runtime and power monitor
            if f_norm.startswith("shared/") or f_norm == "requirements/runtime.txt":
                affected.add(KNOWN_SERVICES["node"])
                affected.add(KNOWN_SERVICES["power_monitor"])

            # Node runtime changes
            elif f_norm.startswith("node_runtime/monitoring/power_monitor.py"):
                affected.add(KNOWN_SERVICES["power_monitor"])
            elif f_norm.startswith("node_runtime/monitoring/telegram_bot.py") or f_norm.startswith("node_runtime/monitoring/telegram_notify.py"):
                if self.is_active(KNOWN_SERVICES["bot"]):
                    affected.add(KNOWN_SERVICES["bot"])
            elif f_norm.startswith("node_runtime/"):
                affected.add(KNOWN_SERVICES["node"])

            # Systemd unit changes require daemon reload
            elif f_norm.startswith("deployment/systemd/"):
                affected.add("systemd-reload")

            # Training pipeline changes affect training service (if running)
            elif f_norm.startswith("ml_pipeline/"):
                if self.is_active(KNOWN_SERVICES["training"]):
                    affected.add(KNOWN_SERVICES["training"])

        return affected

    def restart_affected_services(self, affected_services: Set[str]) -> Dict[str, bool]:
        """Restart all affected services in safe dependency order."""
        results = {}

        if "systemd-reload" in affected_services:
            results["systemd-reload"] = self.daemon_reload()

        # Restart units
        for service in affected_services:
            if service == "systemd-reload":
                continue
            if self.is_active(service) or service == KNOWN_SERVICES["node"]:
                results[service] = self.restart(service)
            else:
                log.info("Service %s is not active; skipping restart", service)
                results[service] = True

        return results
