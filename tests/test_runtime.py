"""
Unit tests for AWARESPAN Node Runtime processing and offline queue.
"""

import tempfile
from pathlib import Path
from shared.models.events import Detection, ThreatEvent
from node_runtime.processing.threat_assessment import ThreatAssessor
from node_runtime.processing.response_selector import ResponseSelector
from node_runtime.communications.backend_sync import IncidentQueue


def test_threat_assessor_tier2_priority():
    assessor = ThreatAssessor(
        tier1_labels={"person", "dog"},
        tier2_labels={"knife", "gun"},
        min_confidence=0.4,
    )
    # Both dog (Tier 1) and knife (Tier 2) detected
    detections = [
        Detection(label="dog", confidence=0.85, bbox=(10, 10, 50, 50)),
        Detection(label="knife", confidence=0.75, bbox=(100, 100, 150, 150)),
    ]
    assessment = assessor.evaluate(detections)
    assert assessment.tier == "tier2"
    assert "knife" in assessment.labels
    assert assessment.is_weapon is True
    assert assessment.threat_level == "CRITICAL"


def test_threat_assessor_tier1():
    assessor = ThreatAssessor(
        tier1_labels={"person", "dog"},
        tier2_labels={"knife", "gun"},
        min_confidence=0.4,
    )
    detections = [
        Detection(label="dog", confidence=0.75, bbox=(10, 10, 50, 50)),
    ]
    assessment = assessor.evaluate(detections)
    assert assessment.tier == "tier1"
    assert "dog" in assessment.labels
    assert assessment.is_weapon is False


def test_threat_assessor_low_confidence():
    assessor = ThreatAssessor(min_confidence=0.5)
    detections = [
        Detection(label="gun", confidence=0.35, bbox=(10, 10, 50, 50)),
    ]
    assessment = assessor.evaluate(detections)
    assert assessment.tier == "none"


def test_response_selector():
    selector = ResponseSelector(siren_enabled=True)
    assessor = ThreatAssessor()
    # Tier 2 triggers alert + siren
    assessment = assessor.evaluate([Detection(label="gun", confidence=0.8, bbox=(0, 0, 10, 10))])
    actions = selector.select_response(assessment)
    assert actions["alert_backend"] is True
    assert actions["alert_telegram"] is True
    assert actions["siren"] is True


def test_sqlite_incident_queue():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = str(Path(tmp_dir) / "test_queue.db")
        q = IncidentQueue(db_path=db_path)
        assert q.depth == 0

        evt = ThreatEvent(
            event_id="evt-test-1",
            ts_ms=1000,
            tier="tier2",
            labels=["knife"],
            max_confidence=0.8,
            action="alert",
        )
        q.enqueue(evt, model="yolov8n.pt")
        assert q.depth == 1

        items = q.dequeue_all()
        assert len(items) == 1
        assert items[0]["id"] == "evt-test-1"
        assert items[0]["event"].tier == "tier2"

        q.mark_success("evt-test-1")
        assert q.depth == 0
