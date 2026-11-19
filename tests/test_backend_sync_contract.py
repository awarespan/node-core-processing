import json
from unittest.mock import Mock

from node_runtime.communications.backend_sync import BackendSync, build_threat_event


def test_rest_payload_preserves_each_detection_and_response(monkeypatch):
    sync = BackendSync(api_url="https://backend.invalid", api_key="test-key", auto_enroll=False)
    sync.node_id = "node-ci-01"
    sync.device_secret = "test-secret"
    sync.headers["X-Node-Id"] = sync.node_id
    sync.headers["X-Device-Secret"] = sync.device_secret
    sync.ready = True
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
    sync = BackendSync(api_url="https://backend.invalid", api_key="test-key", auto_enroll=False)
    sync.node_id = "node-ci-02"
    sync.device_secret = "test-secret"
    sync.ready = True
    sync.headers.update({"X-Node-Id": sync.node_id, "X-Device-Secret": sync.device_secret})
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


def test_backend_enrollment_owns_public_node_identity_and_persists_credentials(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from pathlib import Path

    env_file = tmp_path / ".env"
    env_file.write_text("BACKEND_API_KEY=global-enrollment-key\n")
    settings = SimpleNamespace(
        backend_api_url="https://backend.example.test", backend_api_key="global-enrollment-key",
        node_id="", device_secret="", mqtt_client_id="local-placeholder",
        state_dir=str(tmp_path / "state"), env_file_path=env_file,
    )
    monkeypatch.setattr("node_runtime.communications.backend_sync.get_settings", lambda: settings)
    response = Mock(status_code=200, text="{}")
    response.json.return_value = {
        "nodeId": "node-server-issued-1234",
        "name": "AWARESPAN Edge Node 1234",
        "deviceSecret": "b" * 64,
        "status": "UNKNOWN",
    }
    post = Mock(return_value=response)
    monkeypatch.setattr("node_runtime.communications.backend_sync.requests.post", post)

    sync = BackendSync()

    assert sync.ready is True
    assert sync.node_id == "node-server-issued-1234"
    assert sync.headers["X-Node-Id"] == "node-server-issued-1234"
    assert sync.headers["X-Device-Secret"] == "b" * 64
    assert "X-API-Key" not in sync.headers
    assert settings.mqtt_client_id == sync.node_id
    assert post.call_args.args[0] == "https://backend.example.test/api/v1/nodes/enroll"
    assert post.call_args.kwargs["headers"]["X-API-Key"] == "global-enrollment-key"
    assert post.call_args.kwargs["json"]["installationId"]
    env = env_file.read_text()
    assert "PI_NODE_ID='node-server-issued-1234'" in env
    assert "PI_DEVICE_SECRET='" + ("b" * 64) + "'" in env
    assert "MQTT_CLIENT_ID='node-server-issued-1234'" in env
    assert Path(settings.state_dir, "installation_id").is_file()
