"""
AWARESPAN — Health Check System
Bounded health verification for runtime processes, HTTP/WebSocket endpoints, and hardware status.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Dict
import urllib.request
import urllib.error

from shared.config.settings import get_settings
from shared.logging.logger import get_logger
from shared.utilities.system import get_throttled_state
from node_manager.service_manager import ServiceManager, KNOWN_SERVICES

log = get_logger("node_manager.health_check")


@dataclass
class HealthReport:
    """Consolidated health report across node subsystems."""
    overall_healthy: bool
    checks: Dict[str, bool]
    details: Dict[str, Any]
    message: str


class HealthChecker:
    """Runs bounded diagnostic health checks on AWARESPAN services."""

    def __init__(self):
        self.settings = get_settings()
        self.services = ServiceManager()

    def check_runtime_endpoint(self, timeout_sec: float = 3.0) -> bool:
        """Probe the runtime HTTP/WebSocket health endpoint."""
        url = f"http://127.0.0.1:{self.settings.runtime_port}/health"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AWARESPAN-HealthCheck/2.0"})
            with urllib.request.urlopen(req, timeout=timeout_sec) as response:
                return response.status in (200, 204)
        except urllib.error.HTTPError as exc:
            # 426 Upgrade Required confirms the WebSocket server is active and responding
            return exc.code in (200, 204, 426)
        except Exception:
            # Fallback to TCP socket check
            import socket
            try:
                with socket.create_connection(("127.0.0.1", self.settings.runtime_port), timeout=timeout_sec):
                    return True
            except OSError:
                return False

    def check_event_queue(self) -> bool:
        """Check if SQLite offline queue database is accessible and not corrupted."""
        db_path = self.settings.offline_queue_path
        if not os.path.exists(db_path):
            # Not yet created is normal before first offline event
            return True
        try:
            conn = sqlite3.connect(db_path, timeout=3.0)
            cursor = conn.cursor()
            cursor.execute("PRAGMA quick_check;")
            res = cursor.fetchone()
            conn.close()
            return res and res[0] == "ok"
        except Exception as exc:
            log.warning("Event queue health check failed: %s", exc)
            return False

    def check_services(self) -> Dict[str, bool]:
        """Check if critical systemd services are running."""
        if not self.services.is_available:
            return {"systemd_available": False}
        return {
            "node_service": self.services.is_active(KNOWN_SERVICES["node"]),
            "power_monitor": self.services.is_active(KNOWN_SERVICES["power_monitor"]),
        }

    def verify_node_health(self, max_wait_sec: float = 20.0, poll_interval_sec: float = 2.0) -> HealthReport:
        """
        Poll until node runtime becomes healthy or timeout expires.
        Used after updates and service restarts.
        """
        start = time.time()
        last_report = None

        while time.time() - start < max_wait_sec:
            last_report = self.run_full_check()
            if last_report.overall_healthy:
                return last_report
            time.sleep(poll_interval_sec)

        return last_report or self.run_full_check()

    def run_full_check(self) -> HealthReport:
        """Perform a single comprehensive health check."""
        checks: Dict[str, bool] = {}
        details: Dict[str, Any] = {}

        # 1. Event Queue
        queue_ok = self.check_event_queue()
        checks["event_queue"] = queue_ok

        # 2. Hardware / Power
        power = get_throttled_state()
        details["power"] = power.to_dict()
        checks["power_undervoltage_now"] = not power.undervoltage_now

        # 3. Systemd Services
        service_states = self.check_services()
        details["services"] = service_states
        if self.services.is_available:
            # On production systemd host, node service must be active
            checks["node_service_active"] = service_states.get("node_service", False)

        # 4. Runtime Endpoint
        # If node service is active, test endpoint
        endpoint_ok = self.check_runtime_endpoint(timeout_sec=2.0)
        checks["runtime_endpoint"] = endpoint_ok

        # Determine overall health:
        # If running on systemd host: node service active AND queue ok
        # (Endpoint check is desirable, but might be initializing)
        if self.services.is_available:
            overall_healthy = checks.get("node_service_active", False) and queue_ok
        else:
            # Standalone / dev environment: endpoint or queue
            overall_healthy = queue_ok

        msg = "Node is healthy" if overall_healthy else "Node health check FAILED"
        return HealthReport(
            overall_healthy=overall_healthy,
            checks=checks,
            details=details,
            message=msg,
        )
