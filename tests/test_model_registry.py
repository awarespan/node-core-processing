"""
Unit tests for AWARESPAN Local Model Registry.
"""

import tempfile
from pathlib import Path
from ml_pipeline.registry.model_registry import (
    LocalModelRegistry,
    ModelRegistryEntry,
    ModelState,
)


def test_registry_seed_loading():
    registry = LocalModelRegistry()
    assert len(registry.list_models()) >= 3
    deployed = registry.get_deployed_models()
    assert len(deployed) >= 1
    assert deployed[0].model_id == "awarespan-weapon-yolov8n"


def test_model_lifecycle_transitions():
    with tempfile.TemporaryDirectory() as tmp_dir:
        reg_file = Path(tmp_dir) / "models.json"
        reg = LocalModelRegistry(registry_path=reg_file)

        entry = ModelRegistryEntry(
            model_id="candidate-detector",
            version="1.0.0",
            display_name="Candidate Detector",
            artifact_path="weights/cand.pt",
            sha256="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            framework="ultralytics_yolov8",
            supported_classes=["weapon.firearm.handgun"],
            modality="visual",
            task="object_detection",
            input_requirements={"resolution": [640, 640]},
            state=ModelState.DISCOVERED.value,
        )

        reg.register_model(entry)
        assert reg.get_model("candidate-detector").state == "DISCOVERED"

        # Valid transition: DISCOVERED -> DOWNLOADED
        assert reg.transition_state("candidate-detector", "1.0.0", ModelState.DOWNLOADED, "Weights staged")
        assert reg.get_model("candidate-detector").state == "DOWNLOADED"

        # Invalid transition: DOWNLOADED -> DEPLOYED (cannot deploy without audit/evaluation)
        assert not reg.transition_state("candidate-detector", "1.0.0", ModelState.DEPLOYED, "Skipping checks")

        # Step-by-step valid transitions
        assert reg.transition_state("candidate-detector", "1.0.0", ModelState.AUDITED, "License checked")
        assert reg.transition_state("candidate-detector", "1.0.0", ModelState.LOADED, "Loaded successfully")
        assert reg.transition_state("candidate-detector", "1.0.0", ModelState.EVALUATED, "Benchmarked")
        assert reg.transition_state("candidate-detector", "1.0.0", ModelState.APPROVED, "Approved by engineer")
        assert reg.transition_state("candidate-detector", "1.0.0", ModelState.DEPLOYED, "Deployed to node")

        assert reg.get_model("candidate-detector").state == "DEPLOYED"
