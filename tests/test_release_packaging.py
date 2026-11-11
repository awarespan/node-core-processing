"""
Unit tests for AWARESPAN Model Release Packaging.
"""

import tempfile
import zipfile
from pathlib import Path
from ml_pipeline.packaging.release_manager import ModelReleaseManager
from ml_pipeline.registry.model_registry import (
    LocalModelRegistry,
    ModelRegistryEntry,
    ModelState,
)


def test_model_release_packaging():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        reg_path = tmp_path / "models.json"
        dist_path = tmp_path / "dist"

        # Create dummy weights file
        dummy_weights = tmp_path / "dummy_weights.pt"
        dummy_weights.write_text("DUMMY_WEIGHTS_CONTENT", encoding="utf-8")

        reg = LocalModelRegistry(registry_path=reg_path)
        entry = ModelRegistryEntry(
            model_id="rel-model",
            version="1.0.0",
            display_name="Release Model",
            artifact_path=str(dummy_weights),
            sha256="abcdef123456",
            framework="ultralytics_yolov8",
            supported_classes=["weapon.firearm.handgun"],
            modality="visual",
            task="object_detection",
            input_requirements={},
            state=ModelState.APPROVED.value,
            license_info={"license_name": "MIT", "redistributable": True},
        )
        reg.register_model(entry)

        mgr = ModelReleaseManager(registry=reg, output_dir=dist_path)
        zip_res = mgr.create_release_package(
            release_tag="v0.1.0-test",
            model_ids=["rel-model"],
            evaluation_report={"mAP50": 0.815},
        )

        assert zip_res is not None
        assert zip_res.exists()

        # Inspect zip contents
        with zipfile.ZipFile(zip_res, "r") as zf:
            files = zf.namelist()
            assert "manifest.json" in files
            assert "SHA256SUMS" in files
            assert "evaluation-report.json" in files
            assert "weights/dummy_weights.pt" in files
