"""
AWARESPAN — Update Checker
Inspects remote git repository for new commits, verifies working tree cleanliness, and tests connectivity.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from shared.config.settings import get_settings
from shared.logging.logger import get_logger
from shared.utilities.system import check_internet, get_git_commit, safe_subprocess_run

log = get_logger("node_manager.update_checker")


@dataclass
class UpdateCheckResult:
    """Outcome of an update check."""
    has_update: bool
    current_commit: str
    remote_commit: str
    is_dirty: bool
    can_update: bool
    branch: str
    message: str


class UpdateChecker:
    """Checks for available updates on the target branch without modifying repository files."""

    def __init__(self, repo_path: Optional[Path] = None, branch: Optional[str] = None):
        settings = get_settings()
        self.repo_path = repo_path or settings.repo_root
        self.branch = branch or settings.update_branch

    def is_working_tree_dirty(self) -> bool:
        """Check if there are any uncommitted changes in tracked files."""
        code, stdout, _ = safe_subprocess_run(
            ["git", "status", "--porcelain"],
            timeout=10,
            cwd=str(self.repo_path),
        )
        if code != 0:
            log.warning("git status check failed")
            return False
        # Filter out untracked files (?) if we only care about tracked modifications,
        # but to be extra safe against accidental overwrites, check for any modifications (M, A, D, R, C)
        lines = [line.strip() for line in stdout.splitlines() if line.strip()]
        dirty_tracked = [line for line in lines if not line.startswith("??")]
        return len(dirty_tracked) > 0

    def get_remote_commit(self) -> Optional[str]:
        """Query remote repository using git ls-remote without downloading objects."""
        code, stdout, stderr = safe_subprocess_run(
            ["git", "ls-remote", "origin", f"refs/heads/{self.branch}"],
            timeout=15,
            cwd=str(self.repo_path),
        )
        if code == 0 and stdout.strip():
            # Output format: <sha>\trefs/heads/<branch>
            parts = stdout.strip().split()
            if parts:
                return parts[0]

        log.warning("Failed to obtain remote commit for branch %s: %s", self.branch, stderr.strip())
        return None

    def check(self) -> UpdateCheckResult:
        """Perform a full update check."""
        current_commit = get_git_commit(cwd=str(self.repo_path))

        if not check_internet(timeout=3.0):
            return UpdateCheckResult(
                has_update=False,
                current_commit=current_commit,
                remote_commit="",
                is_dirty=False,
                can_update=False,
                branch=self.branch,
                message="Network unreachable; update check skipped.",
            )

        is_dirty = self.is_working_tree_dirty()
        remote_commit = self.get_remote_commit()

        if not remote_commit:
            return UpdateCheckResult(
                has_update=False,
                current_commit=current_commit,
                remote_commit="",
                is_dirty=is_dirty,
                can_update=False,
                branch=self.branch,
                message="Could not resolve remote commit from origin.",
            )

        has_update = current_commit != remote_commit

        if is_dirty:
            can_update = False
            msg = (
                f"Working tree has uncommitted changes. Auto-update blocked to prevent loss of local work. "
                f"(local: {current_commit[:8]}, remote: {remote_commit[:8]})"
            )
        elif has_update:
            can_update = True
            msg = f"Update available: {current_commit[:8]} -> {remote_commit[:8]} on branch '{self.branch}'."
        else:
            can_update = False
            msg = f"Node is up to date at commit {current_commit[:8]}."

        log.info(msg)
        return UpdateCheckResult(
            has_update=has_update,
            current_commit=current_commit,
            remote_commit=remote_commit,
            is_dirty=is_dirty,
            can_update=can_update,
            branch=self.branch,
            message=msg,
        )
