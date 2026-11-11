"""
Unit tests for AWARESPAN Threat Intelligence & Fusion Subsystem.
"""

import tempfile
from pathlib import Path
from ml_pipeline.fusion.feedback import HumanFeedbackRecord, HumanFeedbackStore
from ml_pipeline.fusion.threat_fusion import ThreatFusionEngine
from ml_pipeline.schema.predictions import StandardDetectionPrediction, StandardModelPrediction


def test_cross_modal_fusion_visual_and_audio():
    engine = ThreatFusionEngine(temporal_window_sec=3.0)

    # 1. Visual handgun prediction
    vis_pred = StandardModelPrediction(
        model_id="yolo-weapon",
        model_version="1.0.0",
        modality="visual",
        task="object_detection",
        taxonomy_version="1.0.0",
        predictions=[
            StandardDetectionPrediction(
                class_id="weapon.firearm.handgun",
                confidence=0.85,
                raw_label="gun",
                bounding_box=[100, 100, 200, 200],
            )
        ],
        inference_latency_ms=65.0,
    )

    # 2. Acoustic gunshot prediction
    audio_pred = StandardModelPrediction(
        model_id="yamnet-audio",
        model_version="1.0.0",
        modality="acoustic",
        task="audio_classification",
        taxonomy_version="1.0.0",
        predictions=[
            StandardDetectionPrediction(
                class_id="audio.threat.gunshot",
                confidence=0.90,
                raw_label="gunshot",
                duration_ms=450.0,
            )
        ],
        inference_latency_ms=12.0,
    )

    assessments = engine.ingest_predictions([vis_pred, audio_pred], current_time_ms=100000)
    assert len(assessments) >= 1

    fused = assessments[0]
    assert fused.is_cross_modal is True
    assert fused.threat_tier == 2
    assert fused.threat_category == "multimodal"
    # Fused confidence should be higher than individual confidences (1 - (1-0.85)*(1-0.90) = 0.985)
    assert fused.confidence > 0.95
    assert "siren" in fused.recommended_actions


def test_shadow_mode_isolation():
    engine = ThreatFusionEngine()

    shadow_pred = StandardModelPrediction(
        model_id="experimental-knife-model",
        model_version="0.1.0",
        modality="visual",
        task="object_detection",
        taxonomy_version="1.0.0",
        predictions=[
            StandardDetectionPrediction(
                class_id="weapon.edged.knife",
                confidence=0.92,
                raw_label="knife",
                bounding_box=[50, 50, 120, 120],
            )
        ],
        inference_latency_ms=50.0,
        metadata={"execution_mode": "shadow"},
    )

    assessments = engine.ingest_predictions([shadow_pred], current_time_ms=200000)
    assert len(assessments) == 1
    ass = assessments[0]
    assert ass.is_shadow_only is True
    # Shadow models must NOT trigger physical siren deterrence!
    assert "siren" not in ass.recommended_actions
    assert "cloud_alert" in ass.recommended_actions


def test_human_feedback_recording():
    with tempfile.TemporaryDirectory() as tmp_dir:
        fb_path = Path(tmp_dir) / "feedback.jsonl"
        store = HumanFeedbackStore(storage_path=fb_path)

        record = HumanFeedbackRecord(
            feedback_id="fb-001",
            assessment_id="fused-vis-100",
            operator_id="operator-benjamin",
            decision="CONFIRMED",
            original_prediction={"class_id": "weapon.firearm.handgun", "confidence": 0.85},
            operator_notes="Handgun clearly visible in right hand",
            model_id="yolo-weapon",
            model_version="1.0.0",
        )

        assert store.record_feedback(record)
        assert fb_path.exists()
        lines = fb_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        assert "CONFIRMED" in lines[0]
