"""
AWARESPAN — MQTT Client
Handles bi-directional messaging with MQTT broker (commands, heartbeats, incident publishing).

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import json
import ssl
import time
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

from shared.config.settings import get_settings
from shared.logging.logger import get_logger
from shared.models.events import ThreatEvent

log = get_logger("node_runtime.mqtt_client")


class PiMqttClient:
    """MQTT Client for edge node communication."""

    def __init__(self, on_command: Optional[Callable[[Dict[str, Any]], None]] = None):
        settings = get_settings()
        self.node_id = settings.node_id
        self.device_secret = settings.device_secret
        self.client_id = settings.mqtt_client_id
        self.broker_url = settings.mqtt_broker_url
        self.username = settings.mqtt_username
        self.password = settings.mqtt_password
        self.use_tls = settings.mqtt_use_tls
        self.ca_cert = settings.mqtt_tls_ca_cert
        self.insecure = settings.mqtt_tls_insecure

        self.on_command = on_command
        self.connected = False
        self._client: Optional[mqtt.Client] = None

        # Topics
        self.topic_incidents = f"sip/{self.node_id}/incidents"
        self.topic_commands = f"sip/{self.node_id}/commands"
        self.topic_heartbeat = f"sip/{self.node_id}/heartbeat"
        self.topic_telemetry = f"sip/{self.node_id}/telemetry"
        self.topic_ack = f"sip/{self.node_id}/ack"
        self._pending_incident_acks: Dict[str, Dict[str, Any]] = {}
        self._pending_ack_lock = threading.Lock()

    def connect(self) -> bool:
        """Establish connection to MQTT broker."""
        if mqtt is None:
            log.warning("paho-mqtt is not installed in this environment; running in mock mode.")
            return False

        if not self.broker_url:
            log.info("MQTT_BROKER_URL not configured; skipping MQTT connection.")
            return False

        parsed = urlparse(self.broker_url if "://" in self.broker_url else f"tcp://{self.broker_url}")
        host = parsed.hostname or "localhost"
        port = parsed.port or (8883 if parsed.scheme in ("ssl", "tls", "mqtts") or self.use_tls else 1883)
        use_ssl = parsed.scheme in ("ssl", "tls", "mqtts") or self.use_tls

        try:
            # Use MQTT v5 or v3.1.1
            self._client = mqtt.Client(client_id=self.client_id, protocol=mqtt.MQTTv311)
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_message = self._on_message

            if self.username:
                self._client.username_pw_set(self.username, self.password)

            if use_ssl:
                ssl_ctx = ssl.create_default_context()
                if self.ca_cert:
                    ssl_ctx.load_verify_locations(cafile=self.ca_cert)
                if self.insecure:
                    ssl_ctx.check_hostname = False
                    ssl_ctx.verify_mode = ssl.CERT_NONE
                self._client.tls_set_context(ssl_ctx)

            log.info("Connecting to MQTT broker at %s:%d (TLS=%s)...", host, port, use_ssl)
            self._client.connect_async(host, port, keepalive=60)
            self._client.loop_start()
            return True
        except Exception as exc:
            log.warning("MQTT connection initialization failed: %s", exc)
            return False

    def disconnect(self) -> None:
        """Disconnect and stop MQTT event loop."""
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
            self.connected = False

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            log.info("MQTT connected successfully to broker (rc=0). Subscribing to command and incident acknowledgement topics")
            client.subscribe(self.topic_commands, qos=1)
            client.subscribe(self.topic_ack, qos=1)
        else:
            self.connected = False
            log.warning("MQTT connection failed with code %d", rc)

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        log.warning("MQTT disconnected (rc=%d)", rc)

    def _on_message(self, client, userdata, msg):
        log.info("MQTT message received on %s", msg.topic)
        try:
            data = json.loads(msg.payload.decode("utf-8"))
            if msg.topic == self.topic_ack:
                incident_id = str(data.get("incidentId", ""))
                with self._pending_ack_lock:
                    pending = self._pending_incident_acks.get(incident_id)
                if pending is not None:
                    pending["success"] = bool(data.get("success", False))
                    pending["event"].set()
                else:
                    log.debug("Received backend acknowledgement for non-pending incident %s", incident_id)
                return
            if self.on_command:
                self.on_command(data)
        except Exception as exc:
            log.warning("Error parsing incoming MQTT message: %s", exc)

    def publish_incident(self, event: ThreatEvent, model: str = "", deterrence: Optional[Dict[str, Any]] = None) -> bool:
        """Publish a backend-compatible incident payload to sip/{nodeId}/incidents."""
        if not self.connected or not self._client:
            return False
        labels = [str(label).lower() for label in event.labels]
        if set(labels) & {"gun", "knife", "weapon", "pistol", "rifle"}:
            threat_type, detection_domain = "WEAPON", "WEAPON"
        elif set(labels) & {"dog", "cat", "horse", "cow", "sheep", "animal"}:
            threat_type, detection_domain = "ANIMAL", "ANIMAL"
        elif set(labels) & {"car", "motorcycle", "bus", "truck", "train", "vehicle"}:
            threat_type, detection_domain = "VEHICLE", None
        elif "person" in labels:
            threat_type, detection_domain = "SUSPICIOUS_BEHAVIOR", "VIOLENCE"
        else:
            threat_type, detection_domain = "UNKNOWN", "UNKNOWN"
        severity = "HIGH" if event.tier in ("tier1", "tier2", "critical", "high") else "MEDIUM"
        detection_time = datetime.fromtimestamp(event.ts_ms / 1000.0, timezone.utc).isoformat()
        payload = {
            "incidentId": event.event_id,
            "idempotencyKey": event.event_id,
            "nodeId": self.node_id,
            "threatType": threat_type,
            "threatSeverity": severity,
            "threatDescription": f"Detected {', '.join(event.labels)} ({event.max_confidence * 100:.1f}%)",
            "confidence": float(event.max_confidence),
            "detectionTime": detection_time,
            "tier": 1 if event.tier in ("tier1", "critical") else 2,
            "modelVersion": model or event.model,
            "detectionDomain": detection_domain,
            "deterrence": deterrence or {},
        }
        pending = {"event": threading.Event(), "success": False}
        with self._pending_ack_lock:
            self._pending_incident_acks[event.event_id] = pending
        try:
            info = self._client.publish(self.topic_incidents, json.dumps(payload), qos=1)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                return False
            # Broker PUBACK is transport-level only; wait for the backend's
            # application ACK emitted after database ingestion commits.
            if hasattr(info, "wait_for_publish"):
                info.wait_for_publish(timeout=1.5)
            if hasattr(info, "is_published") and not info.is_published():
                log.warning("MQTT broker did not confirm publish for incident %s", event.event_id)
                return False
            if not pending["event"].wait(timeout=2.0):
                log.warning("Backend database acknowledgement timed out for incident %s; falling back to REST", event.event_id)
                return False
            if not pending["success"]:
                log.warning("Backend rejected incident %s; falling back to REST", event.event_id)
                return False
            log.info("Backend confirmed database ingestion for incident %s via MQTT", event.event_id)
            return True
        except Exception as exc:
            log.warning("Failed to publish/confirm incident via MQTT: %s", exc)
            return False
        finally:
            with self._pending_ack_lock:
                self._pending_incident_acks.pop(event.event_id, None)

    def publish_heartbeat(self, extra: Optional[Dict[str, Any]] = None) -> bool:
        """Publish heartbeat to sip/{nodeId}/heartbeat."""
        if not self.connected or not self._client:
            return False
        payload = {
            "nodeId": self.node_id,
            "status": "ONLINE",
            "timestamp": int(time.time() * 1000),
            **(extra or {}),
        }
        try:
            info = self._client.publish(self.topic_heartbeat, json.dumps(payload), qos=0)
            return info.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception:
            return False


# Singleton helper
_global_mqtt: Optional[PiMqttClient] = None


def init_mqtt(on_command: Optional[Callable[[Dict[str, Any]], None]] = None) -> PiMqttClient:
    global _global_mqtt
    if _global_mqtt is None:
        _global_mqtt = PiMqttClient(on_command=on_command)
        _global_mqtt.connect()
    return _global_mqtt


def get_mqtt_client() -> Optional[PiMqttClient]:
    return _global_mqtt
