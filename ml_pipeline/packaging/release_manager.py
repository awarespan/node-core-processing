"""
AWARESPAN — Model Release Packager
Packages approved models into versioned GitHub Release bundles with manifests and SHA256 checksums.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import hashlib
import json
import os
import zipfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.logging.logger import get_logger
from ml_pipeline.registry.model_registry import (
    LocalModelRegistry,
    ModelRegistryEntry,
    ModelState,
    get_model_registry,
)

log = get_logger("ml_pipeline.packaging.release")


class ModelReleaseManager:
    """Creates versioned release packages for distribution via GitHub Releases."""

    def __init__(
        self,
        registry: Optional[LocalModelRegistry] = None,
        output_dir: Optional[Path] = None,
    ):
        self.registry = registry or get_model_registry()
        self.output_dir = output_dir or Path("dist") / "releases"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_release_package(
        self,
        release_tag: str,
        model_ids: List[str],
        evaluation_report: Optional[Dict[str, Any]] = None,
    ) -> Optional[Path]:
        """
        Build a release bundle zip containing approved models, manifest.json, and SHA256SUMS.
        Enforces redistribution license checks.
        """
        log.info("Preparing release package for tag: %s", release_tag)
        staged_models: List[ModelRegistryEntry] = []

        for mid in model_ids:
            entry = self.registry.get_model(mid)
            if not entry:
                log.error("Model ID %s not found in registry; skipping", mid)
                continue

            # License check
            lic = entry.license_info or {}
            if not lic.get("redistributable", False):
                log.warning("Model %s has non-redistributable license (%s); excluding from binary bundle", mid, lic.get("license_name"))
                continue

            staged_models.append(entry)

        if not staged_models:
            log.error("No eligible models found for release packaging.")
            return None

        zip_name = f"awarespan-models-{release_tag}.zip"
        zip_path = self.output_dir / zip_name
        manifest_data = {
            "release_tag": release_tag,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "models_count": len(staged_models),
            "models": [m.to_dict() for m in staged_models],
            "evaluation_report": evaluation_report or {},
        }

        sha256_lines = []

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. Manifest
            manifest_json_str = json.dumps(manifest_data, indent=2)
            zf.writestr("manifest.json", manifest_json_str)

            # 2. Add each model artifact
            for m in staged_models:
                src_path = Path(m.artifact_path)
                if not src_path.is_file():
                    log.warning("Artifact %s missing on disk; skipping inclusion in zip", src_path)
                    continue

                arcname = f"weights/{src_path.name}"
                zf.write(src_path, arcname=arcname)

                # Compute checksum
                sha256 = self._compute_sha256(src_path)
                sha256_lines.append(f"{sha256}  {arcname}")

            # 3. Add SHA256SUMS
            zf.writestr("SHA256SUMS", "\n".join(sha256_lines) + "\n")

            # 4. Evaluation report
            if evaluation_report:
                zf.writestr("evaluation-report.json", json.dumps(evaluation_report, indent=2))

        log.info("Successfully built release package: %s (size: %.2f MB)", zip_path, zip_path.stat().st_size / (1024 * 1024))
        return zip_path

    def _compute_sha256(self, path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
