import json
from unittest.mock import Mock

from node_runtime.communications.backend_sync import BackendSync, build_threat_event


def test_rest_payload_preserves_each_detection_and_response(monkeypatch):
    sync = BackendSync(api_url="https://backend.invalid", api_key="test-key")
    sync.node_id = "node-ci-01"
    sync.device_secret = "test-secret"
    sync.headers["X-Node-Id"] = sync.node_id
    sync.headers["X-Device-Secret"] = sync.device_secret
    response = Mock(status_code=201, text="{}")
    post = Mock(return_value=response)
    monkeypatch.setattr("node_runtime.communications.backend_sync.requests.post", post)

    event = build_threat_event(
        tier="tier1", labels=["gun", "knife"], confidence=0.93,
        model="awarespan-weapon-yolov8n:1.0.0", event_id="evt-ci-0001")
    assert sync.send_incident(event, deterrence={"attempted": True, "started": False}) is True

    payload = post.call_args.kwargs["json"]
    assert payload["incidentId"] == "evt-ci-0001"
    assert payload["threatType"] == "WEAPON"
    assert payload["detections"] == [
        {"label": "gun", "confidence": 0.93},
        {"label": "knife", "confidence": 0.93},
    ]
    assert payload["deterrence"] == {"attempted": True, "started": False}
    assert post.call_args.kwargs["headers"]["X-Node-Id"] == "node-ci-01"


def test_rest_payload_fails_closed_when_backend_rejects(monkeypatch):
    sync = BackendSync(api_url="https://backend.invalid", api_key="test-key")
    monkeypatch.setattr(
        "node_runtime.communications.backend_sync.requests.post",
        Mock(return_value=Mock(status_code=401, text="unauthorized")),
    )
    event = build_threat_event("tier1", ["person"], 0.8, event_id="evt-ci-0002")
    assert sync.send_incident(event) is False


def test_mqtt_payload_preserves_detections_and_waits_for_backend_ack():
    import threading
    from types import SimpleNamespace
    from node_runtime.communications.mqtt_client import PiMqttClient

    client = PiMqttClient()
    client.node_id = "node-ci-01"
    client.topic_incidents = "sip/node-ci-01/incidents"
    client.connected = True
    captured = {}

    class FakePublishInfo:
        rc = 0
        def wait_for_publish(self, timeout=None):
            return None
        def is_published(self):
            return True

    class FakeMqtt:
        def publish(self, topic, payload, qos):
            captured["topic"] = topic
            captured["payload"] = json.loads(payload)
            pending = client._pending_incident_acks["evt-ci-0003"]
            pending["success"] = True
            pending["event"].set()
            return FakePublishInfo()

    client._client = FakeMqtt()
    event = build_threat_event(
        tier="tier1", labels=["gun", "knife"], confidence=0.88,
        event_id="evt-ci-0003")

    assert client.publish_incident(event, deterrence={"attempted": False}) is True
    assert captured["topic"] == "sip/node-ci-01/incidents"
    assert [item["label"] for item in captured["payload"]["detections"]] == ["gun", "knife"]
    assert captured["payload"]["deterrence"] == {"attempted": False}
