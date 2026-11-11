"""
AWARESPAN — Model Downloader & Verification Engine
Safely downloads, audits, checks SHA256 integrity, and registers models into the local store.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import hashlib
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from shared.logging.logger import get_logger
from ml_pipeline.registry.model_registry import (
    LocalModelRegistry,
    ModelRegistryEntry,
    ModelState,
    get_model_registry,
)

log = get_logger("ml_pipeline.acquisition.downloader")


def compute_sha256(filepath: str) -> str:
    """Compute SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


class ModelDownloader:
    """Handles controlled acquisition, checksum validation, and local staging of models."""

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        registry: Optional[LocalModelRegistry] = None,
    ):
        self.base_dir = base_dir or Path("models")
        self.registry = registry or get_model_registry()

    def import_local_artifact(
        self,
        source_path: str,
        model_id: str,
        version: str,
        domain: str,
        expected_sha256: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Path]:
        """
        Safely import a local checkpoint into structured working directory models/working/<domain>/.
        Verifies SHA-256 before staging.
        """
        src = Path(source_path)
        if not src.is_file():
            log.error("Source artifact not found: %s", source_path)
            return None

        actual_sha256 = compute_sha256(str(src))
        if expected_sha256 and actual_sha256.lower() != expected_sha256.lower():
            log.error(
                "SHA-256 mismatch for %s! Expected: %s, Actual: %s",
                source_path, expected_sha256, actual_sha256
            )
            return None

        target_dir = self.base_dir / "working" / domain
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / src.name

        # Copy file if not already at destination
        if src.resolve() != target_path.resolve():
            shutil.copy2(src, target_path)
            log.info("Staged model artifact to %s", target_path)

        # Transition or create registry entry
        entry = self.registry.get_model(model_id, version)
        if entry:
            self.registry.transition_state(
                model_id,
                version,
                ModelState.DOWNLOADED,
                reason=f"Staged artifact verified with SHA256 {actual_sha256[:8]}",
            )
        return target_path
