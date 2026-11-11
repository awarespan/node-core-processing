"""
Unit tests for AWARESPAN ML Pipeline packaging and safety toggles.
"""

import json
import tempfile
from pathlib import Path
from ml_pipeline.packaging.model_packager import ModelPackager, compute_sha256
from shared.config.settings import get_settings


def test_ml_training_disabled_by_default():
    settings = get_settings()
    assert settings.ml_training_enabled is False


def test_model_packager():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a dummy weights file
        dummy_weights = Path(tmp_dir) / "test_weights.pt"
        dummy_weights.write_bytes(b"AWARESPAN_MODEL_WEIGHTS_MOCK_BYTES_12345")

        out_dir = Path(tmp_dir) / "packaged"
        packager = ModelPackager()
        res = packager.package_model(
            weights_path=str(dummy_weights),
            model_name="yolov8n_test",
            version="1.0.0",
            classes=["knife", "gun"],
            confidence_threshold=0.5,
            target_dir=str(out_dir),
        )

        assert res is not None
        assert res.exists()
        metadata_file = out_dir / "yolov8n_test_metadata.json"
        assert metadata_file.exists()

        with open(metadata_file) as f:
            meta = json.load(f)
            assert meta["model_name"] == "yolov8n_test"
            assert meta["num_classes"] == 2
            assert meta["confidence_threshold"] == 0.5
            assert len(meta["sha256"]) == 64
