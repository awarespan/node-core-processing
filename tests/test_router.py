"""
Unit tests for AWARESPAN Inference Router.
"""

from ml_pipeline.adapters.mock_adapter import MockThreatAdapter
from ml_pipeline.inference.router import HardwareBudget, InferenceRouter
from ml_pipeline.registry.model_registry import (
    LocalModelRegistry,
    ModelRegistryEntry,
    ModelState,
)
from ml_pipeline.schema.predictions import StandardDetectionPrediction


def test_router_visual_dispatch():
    reg = LocalModelRegistry()
    budget = HardwareBudget(max_concurrent_visual=1, enable_shadow_models=False)
    router = InferenceRouter(registry=reg, budget=budget)

    # Register mock visual adapter matching deployed model
    adapter = MockThreatAdapter(
        model_id="awarespan-weapon-yolov8n",
        modality="visual",
        synthetic_detections=[
            StandardDetectionPrediction(
                class_id="weapon.firearm.handgun",
                confidence=0.88,
                raw_label="gun",
            )
        ],
    )
    router.register_adapter(adapter)

    preds = router.route_visual(frame=None)
    assert len(preds) == 1
    assert preds[0].model_id == "awarespan-weapon-yolov8n"
    assert len(preds[0].predictions) == 1
    assert preds[0].predictions[0].class_id == "weapon.firearm.handgun"


def test_router_cross_modal_trigger():
    reg = LocalModelRegistry()
    router = InferenceRouter(registry=reg)

    audio_adapter = MockThreatAdapter(
        model_id="awarespan-yamnet-audio",
        modality="acoustic",
        synthetic_detections=[
            StandardDetectionPrediction(
                class_id="audio.threat.gunshot",
                confidence=0.95,
                raw_label="gunshot",
            )
        ],
    )
    router.register_adapter(audio_adapter)

    assert router.is_cross_modal_active() is False
    router.route_audio(audio_data=None)
    # Gunshot detected triggers cross-modal alert
    assert router.is_cross_modal_active(window_sec=2.0) is True
