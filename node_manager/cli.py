"""
AWARESPAN — Node Manager CLI
Command-line interface for update management, health checks, rollbacks, and diagnostic status.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import argparse
import json
import sys
from datetime import datetime

from shared.config.settings import get_settings
from shared.logging.logger import get_logger
from shared.utilities.system import get_git_commit, get_raspberry_pi_model, get_throttled_state
from node_manager.updater.version_state import VersionStateManager
from node_manager.updater.update_checker import UpdateChecker
from node_manager.updater.update_executor import UpdateExecutor
from node_manager.updater.rollback import RollbackManager
from node_manager.health_check import HealthChecker
from node_manager.service_manager import ServiceManager

log = get_logger("node_manager.cli")


def cmd_status(args):
    """Print complete node diagnostic status."""
    settings = get_settings()
    state_mgr = VersionStateManager()
    state = state_mgr.get_state()
    services = ServiceManager()
    power = get_throttled_state()
    hw_model = get_raspberry_pi_model()
    current_git = get_git_commit(cwd=str(settings.repo_root))

    print("\n" + "=" * 60)
    print(" AWARESPAN Node Core — Diagnostic Status")
    print(" Tagline: Awareness Without Boundaries.")
    print(" Official: An AI-Powered Safety Device.")
    print("=" * 60)
    print(f" Node ID:           {settings.node_id}")
    print(f" Hardware:          {hw_model}")
    print(f" Working Directory: {settings.repo_root}")
    print(f" Canonical .env:    {settings.env_file_path or 'NOT FOUND'}")
    print(f" Git HEAD Commit:   {current_git}")
    print(f" Tracking Branch:   {settings.update_branch}")
    print("-" * 60)
    print(" [Updater State]")
    print(f" Status:            {state.status}")
    print(f" Target Commit:     {state.target_commit or 'None'}")
    print(f" Last Check:        {state.last_check or 'Never'}")
    print(f" Last Update:       {state.last_update or 'Never'}")
    print(f" Last Error:        {state.last_error or 'None'}")
    print(f" Rollback Target:   {state.rollback_target or 'None'}")
    print("-" * 60)
    print(" [Hardware & Power Health]")
    print(f" CPU Temperature:   {f'{power.temp_c:.1f} °C' if power.temp_c else 'N/A'}")
    print(f" Throttled (raw):   {power.throttled_raw}")
    print(f" Undervoltage NOW:  {'⚠️ YES (THROTTLED)' if power.undervoltage_now else 'No (OK)'}")
    print(f" Undervoltage PAST: {'⚠️ YES' if power.undervoltage_occurred else 'No'}")
    print(f" Frequency Capped:  {'⚠️ YES' if power.freq_capped_now else 'No'}")
    print("-" * 60)
    print(" [Systemd Services]")
    for name, info in services.get_all_statuses().items():
        act = "🟢 ACTIVE" if info["active"] else "⚪ INACTIVE"
        enb = "ENABLED" if info["enabled"] else "DISABLED"
        print(f" {info['unit']:<32} {act} ({enb})")
    print("=" * 60 + "\n")


def cmd_check(args):
    """Check for updates on GitHub."""
    checker = UpdateChecker()
    res = checker.check()
    state_mgr = VersionStateManager()
    state_mgr.record_check(res.remote_commit, res.has_update)

    print("\n" + "-" * 50)
    print(f" Update Check Result for branch '{res.branch}':")
    print(f" Local Commit:   {res.current_commit[:8]}")
    print(f" Remote Commit:  {res.remote_commit[:8] if res.remote_commit else 'Unknown'}")
    print(f" Update Avail:   {'YES' if res.has_update else 'NO'}")
    print(f" Working Dirty:  {'⚠️ YES' if res.is_dirty else 'NO'}")
    print(f" Can Auto-Update:{'YES' if res.can_update else 'NO'}")
    print(f" Message:        {res.message}")
    print("-" * 50 + "\n")


def cmd_update(args):
    """Execute update cycle."""
    executor = UpdateExecutor()
    success = executor.execute_update(force=args.force)
    sys.exit(0 if success else 1)


def cmd_check_and_update(args):
    """Entry point for systemd timer."""
    settings = get_settings()
    if not settings.auto_update_enabled:
        log.info("Auto-update is disabled in settings; exiting.")
        return
    executor = UpdateExecutor()
    executor.execute_update(force=False)


def cmd_rollback(args):
    """Execute rollback to previous stable commit."""
    mgr = RollbackManager()
    success = mgr.rollback(target_commit=args.commit, reason=args.reason)
    sys.exit(0 if success else 1)


def cmd_health(args):
    """Run health check diagnostics."""
    checker = HealthChecker()
    report = checker.run_full_check()
    status_str = "HEALTHY" if report.overall_healthy else "UNHEALTHY"
    print(f"\nNode Health: [{status_str}] - {report.message}")
    print(json.dumps(report.checks, indent=2))
    sys.exit(0 if report.overall_healthy else 1)


def main():
    parser = argparse.ArgumentParser(description="AWARESPAN Node Manager CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    p_status = subparsers.add_parser("status", help="Show node diagnostic status")
    p_status.set_defaults(func=cmd_status)

    # check
    p_check = subparsers.add_parser("check", help="Check for available git updates")
    p_check.set_defaults(func=cmd_check)

    # update
    p_update = subparsers.add_parser("update", help="Perform staged update")
    p_update.add_argument("--force", action="store_true", help="Force update even if commits match")
    p_update.set_defaults(func=cmd_update)

    # check-and-update (used by systemd timer)
    p_auto = subparsers.add_parser("check-and-update", help="Run automated update check and install")
    p_auto.set_defaults(func=cmd_check_and_update)

    # rollback
    p_rb = subparsers.add_parser("rollback", help="Roll back to previous or specified commit")
    p_rb.add_argument("--commit", default=None, help="Explicit commit SHA to restore")
    p_rb.add_argument("--reason", default="Manual rollback invoked by operator", help="Rollback reason")
    p_rb.set_defaults(func=cmd_rollback)

    # health
    p_health = subparsers.add_parser("health", help="Run health check probe")
    p_health.set_defaults(func=cmd_health)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
