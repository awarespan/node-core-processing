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
            log.info("MQTT connected successfully to broker (rc=0). Subscribing to %s", self.topic_commands)
            client.subscribe(self.topic_commands, qos=1)
        else:
            self.connected = False
            log.warning("MQTT connection failed with code %d", rc)

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        log.warning("MQTT disconnected (rc=%d)", rc)

    def _on_message(self, client, userdata, msg):
        log.info("MQTT message received on %s: %s", msg.topic, msg.payload[:100])
        if self.on_command:
            try:
                data = json.loads(msg.payload.decode("utf-8"))
                self.on_command(data)
            except Exception as exc:
                log.warning("Error parsing incoming MQTT command: %s", exc)

    def publish_incident(self, event: ThreatEvent, model: str = "") -> bool:
        """Publish threat incident to sip/{nodeId}/incidents."""
        if not self.connected or not self._client:
            return False
        payload = {
            "nodeId": self.node_id,
            "eventId": event.event_id,
            "tier": event.tier,
            "labels": event.labels,
            "maxConfidence": event.max_confidence,
            "action": event.action,
            "latencyMs": event.latency_ms,
            "frameId": event.frame_id,
            "model": model or event.model,
            "timestamp": event.ts_ms,
        }
        try:
            info = self._client.publish(self.topic_incidents, json.dumps(payload), qos=1)
            return info.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as exc:
            log.warning("Failed to publish incident via MQTT: %s", exc)
            return False

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
