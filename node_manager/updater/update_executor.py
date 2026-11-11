"""
AWARESPAN — Update Executor
Orchestrates safe, atomic, staged updates with pre-validation, selective restarts, and automatic rollback.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Set
import urllib.request
import json

from shared.config.settings import get_settings
from shared.logging.logger import get_logger
from shared.utilities.system import FileLock, get_git_commit, safe_subprocess_run
from node_manager.updater.version_state import VersionStateManager
from node_manager.updater.update_checker import UpdateChecker, UpdateCheckResult
from node_manager.service_manager import ServiceManager
from node_manager.health_check import HealthChecker
from node_manager.updater.rollback import RollbackManager

log = get_logger("node_manager.update_executor")


class UpdateExecutor:
    """Safely executes updates against the active git checkout."""

    def __init__(self):
        self.settings = get_settings()
        self.state_manager = VersionStateManager()
        self.checker = UpdateChecker(self.settings.repo_root, self.settings.update_branch)
        self.services = ServiceManager()
        self.health = HealthChecker()
        self.rollback_mgr = RollbackManager(self.state_manager)

    def execute_update(self, force: bool = False) -> bool:
        """
        Run the complete update sequence:
        Lock -> Check -> Fetch -> Pre-validate -> Merge -> Deps -> Restart -> Health Check.
        Rolls back automatically on failure.
        """
        lock = FileLock(self.settings.lock_file, timeout_sec=10.0)
        try:
            with lock:
                return self._run_staged_update(force=force)
        except TimeoutError:
            log.warning("Update lock held by another process; aborting update run.")
            return False

    def _run_staged_update(self, force: bool = False) -> bool:
        log.info("Starting AWARESPAN staged update cycle...")

        # 1. Update Check
        check_result: UpdateCheckResult = self.checker.check()
        self.state_manager.record_check(check_result.remote_commit, check_result.has_update)

        if not check_result.has_update and not force:
            log.info("No update available. Repository is current.")
            return True

        if not check_result.can_update and not force:
            log.warning("Update blocked: %s", check_result.message)
            return False

        current_sha = check_result.current_commit
        target_sha = check_result.remote_commit
        repo_dir = str(self.settings.repo_root)

        log.info("Update proceeding: %s -> %s on branch %s", current_sha[:8], target_sha[:8], self.settings.update_branch)
        self.state_manager.start_update(target_sha, current_sha)

        # 2. Fetch origin
        code, stdout, stderr = safe_subprocess_run(
            ["git", "fetch", "origin", self.settings.update_branch],
            timeout=45,
            cwd=repo_dir,
        )
        if code != 0:
            err = f"git fetch failed: {stderr}"
            log.error(err)
            self.state_manager.finish_update(False, current_sha, [], err)
            return False

        # 3. Inspect changed files
        code, stdout, stderr = safe_subprocess_run(
            ["git", "diff", "--name-only", "HEAD", f"origin/{self.settings.update_branch}"],
            timeout=15,
            cwd=repo_dir,
        )
        if code != 0:
            err = f"git diff failed: {stderr}"
            log.error(err)
            self.state_manager.finish_update(False, current_sha, [], err)
            return False

        changed_files = [line.strip() for line in stdout.splitlines() if line.strip()]
        log.info("Changed files in update (%d files): %s", len(changed_files), ", ".join(changed_files[:10]))

        # 4. Pre-validation: Syntax check on incoming Python files
        syntax_ok, syntax_err = self._prevalidate_incoming_code(changed_files)
        if not syntax_ok:
            err = f"Pre-validation failed (syntax error in incoming code): {syntax_err}"
            log.error(err)
            self.state_manager.finish_update(False, current_sha, [], err)
            self._notify_telegram(f"❌ <b>AWARESPAN Update Rejected</b>\nPre-validation failed: {syntax_err}")
            return False

        # 5. Apply update via fast-forward merge
        code, stdout, stderr = safe_subprocess_run(
            ["git", "merge", "--ff-only", f"origin/{self.settings.update_branch}"],
            timeout=30,
            cwd=repo_dir,
        )
        if code != 0:
            err = f"Fast-forward merge failed: {stderr}"
            log.error(err)
            # Rollback to pre-update commit
            self.rollback_mgr.rollback(current_sha, reason=err)
            return False

        new_sha = get_git_commit(cwd=repo_dir)
        log.info("Repository updated to %s", new_sha[:8])

        # 6. Dependency update if requirements changed
        if "requirements/runtime.txt" in changed_files:
            log.info("Runtime requirements changed; updating dependencies...")
            req_path = self.settings.repo_root / "requirements" / "runtime.txt"
            code, _, stderr = safe_subprocess_run(
                [sys.executable, "-m", "pip", "install", "--no-warn-script-location", "-r", str(req_path)],
                timeout=240,
                cwd=repo_dir,
            )
            if code != 0:
                log.warning("Dependency install reported issues: %s", stderr)

        # 7. Determine affected services
        affected_services = self.services.determine_affected_services(changed_files)
        log.info("Affected services requiring restart: %s", ", ".join(affected_services) or "none")

        # 8. Restart affected services
        if affected_services:
            self.services.restart_affected_services(affected_services)

        # 9. Health verification
        log.info("Verifying node health post-update...")
        health_report = self.health.verify_node_health(max_wait_sec=25.0, poll_interval_sec=2.0)

        if not health_report.overall_healthy:
            err = f"Post-update health check failed: {health_report.message}"
            log.error("%s. Triggering automatic rollback to %s...", err, current_sha[:8])
            self.rollback_mgr.rollback(current_sha, reason=err)
            return False

        # 10. Update succeeded!
        log.info("Update succeeded and verified healthy at commit %s", new_sha[:8])
        self.state_manager.finish_update(True, new_sha, list(affected_services))
        self._notify_telegram(
            f"✅ <b>AWARESPAN Update Successful</b>\n"
            f"Node: <code>{self.settings.node_id}</code>\n"
            f"Commit: <code>{new_sha[:8]}</code>\n"
            f"Affected: {', '.join(affected_services) or 'None'}\n"
            f"Health: Healthy"
        )
        return True

    def _prevalidate_incoming_code(self, changed_files: List[str]) -> (bool, str):
        """
        Check that all changed Python files in origin/<branch> can be compiled without syntax errors
        before modifying the active repository.
        """
        py_files = [f for f in changed_files if f.endswith(".py")]
        if not py_files:
            return True, ""

        with tempfile.TemporaryDirectory() as tmp_dir:
            for py_file in py_files:
                code, content, _ = safe_subprocess_run(
                    ["git", "show", f"origin/{self.settings.update_branch}:{py_file}"],
                    timeout=10,
                    cwd=str(self.settings.repo_root),
                )
                if code != 0:
                    continue  # File might have been deleted

                tmp_path = Path(tmp_dir) / Path(py_file).name
                tmp_path.write_text(content, encoding="utf-8")

                # Test compilation
                code, _, stderr = safe_subprocess_run(
                    [sys.executable, "-m", "py_compile", str(tmp_path)],
                    timeout=10,
                )
                if code != 0:
                    return False, f"Syntax error in {py_file}: {stderr.strip()}"

        return True, ""

    def _notify_telegram(self, message: str) -> None:
        """Send update notification to Telegram."""
        if not self.settings.bot_token or not self.settings.primary_chat_id:
            return
        try:
            url = f"https://api.telegram.org/bot{self.settings.bot_token}/sendMessage"
            payload = json.dumps({
                "chat_id": self.settings.primary_chat_id,
                "text": message,
                "parse_mode": "HTML",
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
        except Exception as exc:
            log.warning("Failed to send Telegram update notification: %s", exc)
