"""
AWARESPAN — Version State Manager
Tracks installed revision, target revisions, update statuses, history, and rollback targets.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.config.settings import get_settings
from shared.logging.logger import get_logger
from shared.models.events import UpdateState
from shared.utilities.system import get_git_commit

log = get_logger("node_manager.version_state")


class VersionStateManager:
    """Manages persistent state file for the node updater."""

    def __init__(self, state_file_override: Optional[str] = None):
        settings = get_settings()
        if state_file_override:
            self.state_file = Path(state_file_override)
        else:
            primary_path = Path(settings.state_dir) / "version_state.json"
            try:
                primary_path.parent.mkdir(parents=True, exist_ok=True)
                # Test write capability
                if os.access(primary_path.parent, os.W_OK):
                    self.state_file = primary_path
                else:
                    raise PermissionError("No write access to state_dir")
            except (PermissionError, OSError):
                # Fallback to repository state directory
                fallback_path = settings.repo_root / "state" / "version_state.json"
                fallback_path.parent.mkdir(parents=True, exist_ok=True)
                self.state_file = fallback_path

        self.state: UpdateState = self._load()

    def _load(self) -> UpdateState:
        """Load state from disk or initialize fresh state from git."""
        current_git = get_git_commit(cwd=str(get_settings().repo_root))
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return UpdateState(
                        current_commit=data.get("current_commit", current_git),
                        target_commit=data.get("target_commit", ""),
                        status=data.get("status", "IDLE"),
                        last_check=data.get("last_check", ""),
                        last_update=data.get("last_update", ""),
                        last_error=data.get("last_error", ""),
                        rollback_target=data.get("rollback_target", ""),
                        history=data.get("history", []),
                    )
            except Exception as exc:
                log.warning("Failed to parse state file %s: %s (initializing fresh)", self.state_file, exc)

        # Initialize fresh state
        state = UpdateState(
            current_commit=current_git,
            status="IDLE",
            last_check=datetime.now(timezone.utc).isoformat(),
        )
        self._save(state)
        return state

    def _save(self, state: UpdateState) -> None:
        """Write state to disk safely with atomic temp file rename."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = self.state_file.with_suffix(".tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(state.to_dict(), f, indent=2)
            tmp_file.replace(self.state_file)
        except Exception as exc:
            log.error("Failed to write version state to %s: %s", self.state_file, exc)

    def get_state(self) -> UpdateState:
        """Return current in-memory state."""
        return self.state

    def record_check(self, target_commit: str, has_update: bool) -> None:
        """Record an update check event."""
        self.state.last_check = datetime.now(timezone.utc).isoformat()
        self.state.target_commit = target_commit
        if not has_update and self.state.status != "UPDATING":
            self.state.status = "IDLE"
            self.state.last_error = ""
        self._save(self.state)

    def start_update(self, target_commit: str, rollback_commit: str) -> None:
        """Mark update as in-progress."""
        self.state.status = "UPDATING"
        self.state.target_commit = target_commit
        self.state.rollback_target = rollback_commit
        self.state.last_error = ""
        self._save(self.state)

    def finish_update(
        self,
        success: bool,
        new_commit: str,
        affected_services: List[str],
        error_msg: str = "",
    ) -> None:
        """Record update outcome and append to history."""
        now = datetime.now(timezone.utc).isoformat()
        entry: Dict[str, Any] = {
            "timestamp": now,
            "from_commit": self.state.current_commit,
            "to_commit": new_commit,
            "status": "SUCCESS" if success else "FAILED",
            "affected_services": affected_services,
            "error": error_msg,
        }
        self.state.history.append(entry)
        # Retain last 50 history entries
        self.state.history = self.state.history[-50:]

        if success:
            self.state.status = "SUCCESS"
            self.state.current_commit = new_commit
            self.state.last_update = now
            self.state.last_error = ""
        else:
            self.state.status = "FAILED"
            self.state.last_error = error_msg

        self._save(self.state)

    def record_rollback(self, rolled_back_to: str, reason: str) -> None:
        """Record that a rollback occurred."""
        now = datetime.now(timezone.utc).isoformat()
        entry: Dict[str, Any] = {
            "timestamp": now,
            "event": "ROLLBACK",
            "from_commit": self.state.current_commit,
            "to_commit": rolled_back_to,
            "reason": reason,
        }
        self.state.history.append(entry)
        self.state.history = self.state.history[-50:]
        self.state.status = "ROLLED_BACK"
        self.state.current_commit = rolled_back_to
        self.state.last_update = now
        self.state.last_error = f"Rollback triggered: {reason}"
        self._save(self.state)
