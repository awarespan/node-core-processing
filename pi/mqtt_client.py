#!/usr/bin/env python3
"""
MQTT client for SIP Pi ↔ backend communication.

Architecture: Both Pi and backend connect OUT to the MQTT broker.
- Commands flow:  Backend → MQTT Broker → Pi  (Pi subscribes to sip/{nodeId}/commands)
- Incidents flow: Pi → MQTT Broker → Backend  (Pi publishes to sip/{nodeId}/incidents)
- Heartbeats:     Pi → MQTT Broker → Backend  (Pi publishes to sip/{nodeId}/heartbeat)

This eliminates the need for the backend to reach the Pi's dynamic IP.
"""

import asyncio
import json
import logging
import os
import sqlite3
import ssl
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import paho.mqtt.client as mqtt
import dotenv

log = logging.getLogger("mqtt_client")

# Load env from ~/edge-ai/.env (same as telegram_notify.py)
dotenv.load_dotenv(os.path.join(os.path.expanduser("~"), "edge-ai", ".env"))


# ─── Config ────────────────────────────────────────────────────────────────────

def get_env(key: str, default: str = "") -> str:
    val = os.getenv(key)
    return val if val is not None else default


BROKER_URL = get_env("MQTT_BROKER_URL", "tcp://broker.hivemq.com:1883")
MQTT_USERNAME = get_env("MQTT_USERNAME", "")
MQTT_PASSWORD = get_env("MQTT_PASSWORD", "")
CLIENT_ID = get_env("MQTT_CLIENT_ID", f"sip-pi-{uuid.getnode():012x}")
NODE_ID = get_env("PI_NODE_ID", "sip-pi-001")
DEVICE_SECRET = get_env("PI_DEVICE_SECRET", "changeme")
BACKEND_API_URL = get_env("BACKEND_API_URL", "http://localhost:8080")
BACKEND_API_KEY = get_env("BACKEND_API_KEY", "")

QOS_INCIDENT = 1   # At least once for incidents
QOS_COMMAND = 2    # Exactly once for commands


# ─── Offline Queue (SQLite) ────────────────────────────────────────────────────

class OfflineQueue:
    """
    SQLite queue for incidents when MQTT/backend is unavailable.
    Replays queued items on reconnect.
    """

    def __init__(self, db_path: str = "/tmp/sip_offline_queue.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS offline_incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    qos INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_attempt REAL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON offline_incidents(created_at)")

    def enqueue(self, topic: str, payload: Dict, qos: int = 1) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO offline_incidents (topic, payload, qos, created_at) VALUES (?, ?, ?, ?)",
                (topic, json.dumps(payload), qos, time.time())
            )
            return cur.lastrowid

    def dequeue_all(self) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, topic, payload, qos FROM offline_incidents ORDER BY created_at ASC"
            ).fetchall()
        return [{"id": r[0], "topic": r[1], "payload": json.loads(r[2]), "qos": r[3]} for r in rows]

    def mark_sent(self, row_id: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM offline_incidents WHERE id = ?", (row_id,))

    def mark_failed(self, row_id: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE offline_incidents SET attempts = attempts + 1, last_attempt = ? WHERE id = ?",
                (time.time(), row_id)
            )

    def purge_old(self, max_age_hours: int = 24, max_attempts: int = 10):
        cutoff = time.time() - max_age_hours * 3600
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM offline_incidents WHERE created_at < ? OR attempts > ?",
                (cutoff, max_attempts)
            )

    @property
    def depth(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM offline_incidents").fetchone()[0]


# ─── MQTT Client ───────────────────────────────────────────────────────────────

class PiMqttClient:
    """
    MQTT client that runs on the Raspberry Pi.
    - Publishes incidents and heartbeats to the backend
    - Subscribes to commands from the backend
    - Queues incidents offline when disconnected
    """

    def __init__(self):
        self.queue = OfflineQueue()
        self.client = mqtt.Client(client_id=CLIENT_ID, protocol=mqtt.MQTTv311)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_publish = self._on_publish

        if MQTT_USERNAME:
            self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

        # Will be set by command callbacks
        self.command_callback: Optional[callable] = None
        self.connected = False

    # ── Connection lifecycle ──────────────────────────────────────────────────

    def connect(self, timeout: int = 30) -> bool:
        try:
            log.info("Connecting to MQTT broker at %s (client_id=%s)", BROKER_URL, CLIENT_ID)

            # Parse protocol and host/port
            proto = BROKER_URL.split("://")[0] if "://" in BROKER_URL else "tcp"
            host_part = BROKER_URL.split("://")[1] if "://" in BROKER_URL else BROKER_URL
            host = host_part.rsplit(":", 1)[0] if ":" in host_part else host_part
            port = int(host_part.rsplit(":", 1)[1]) if ":" in host_part else 8883 if proto in ("ssl", "mqtts") else 1883

            # Apply TLS for ssl:// and mqtts://
            if proto in ("ssl", "mqtts"):
                ssl_ctx = ssl.create_default_context()
                tls_ca = get_env("MQTT_TLS_CA_CERT", "")
                if tls_ca:
                    ssl_ctx.load_verify_locations(tls_ca)
                self.client.tls_set_context(ssl_ctx)
                if get_env("MQTT_TLS_INSECURE", "false").lower() == "true":
                    ssl_ctx.check_hostname = False
                    ssl_ctx.verify_mode = ssl.CERT_NONE

            self.client.connect_async(host, port, keepalive=60)
            self.client.loop_start()
            # Wait for connection
            for _ in range(timeout * 2):
                if self.connected:
                    return True
                time.sleep(0.5)
            log.warning("MQTT connection timeout — running in offline mode")
            return False
        except Exception as exc:
            log.error("MQTT connection failed: %s — running in offline mode", exc)
            return False

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
        self.connected = False

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.connected = True
            log.info("MQTT connected. Subscribing to commands on sip/%s/commands", NODE_ID)
            # Subscribe to our own command topic (QoS 2 for exactly-once delivery)
            topic = f"sip/{NODE_ID}/commands"
            client.subscribe(topic, qos=QOS_COMMAND)
            log.info("Subscribed to %s", topic)

            # Replay offline queue
            self._replay_offline_queue()
        else:
            log.warning("MQTT connect failed with rc=%d", rc)

    def _on_disconnect(self, client, userdata, rc, properties=None):
        self.connected = False
        if rc != 0:
            log.warning("MQTT unexpected disconnect (rc=%d) — incidents will queue locally", rc)

    def _on_message(self, client, userdata, msg: mqtt.MQTTMessage):
        try:
            payload = json.loads(msg.payload.decode())
            log.debug("Command received on %s: %s", msg.topic, payload)
            if self.command_callback:
                self.command_callback(payload)
            # Send ACK back
            self._send_command_ack(payload.get("commandId"), True)
        except Exception as exc:
            log.error("Error handling command message: %s", exc)

    def _on_publish(self, client, userdata, mid):
        log.debug("Message id %d published", mid)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_command_callback(self, callback: callable):
        """Register a callback for incoming commands."""
        self.command_callback = callback

    def publish_incident(self, incident: Dict) -> bool:
        """
        Publish an incident to sip/{nodeId}/incidents.
        Queues locally if disconnected.
        """
        topic = f"sip/{NODE_ID}/incidents"

        # Add metadata
        incident["nodeId"] = NODE_ID
        incident["idempotencyKey"] = incident.get("idempotencyKey") or f"{NODE_ID}-{incident.get('incidentId', uuid.uuid4().hex[:12])}"
        incident["syncStatus"] = "PENDING"

        if not self.connected:
            log.info("MQTT offline — queueing incident (queue depth=%d)", self.queue.depth)
            self.queue.enqueue(topic, incident, QOS_INCIDENT)
            return False

        try:
            result = self.client.publish(topic, json.dumps(incident), qos=QOS_INCIDENT)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                log.debug("Published incident %s to %s", incident.get("incidentId"), topic)
                return True
            else:
                log.warning("MQTT publish failed rc=%d — queueing", result.rc)
                self.queue.enqueue(topic, incident, QOS_INCIDENT)
                return False
        except Exception as exc:
            log.warning("MQTT publish exception: %s — queueing", exc)
            self.queue.enqueue(topic, incident, QOS_INCIDENT)
            return False

    def publish_heartbeat(self, extra: Optional[Dict] = None) -> bool:
        """Publish a heartbeat to sip/{nodeId}/heartbeat."""
        if not self.connected:
            return False

        topic = f"sip/{NODE_ID}/heartbeat"
        payload = {
            "nodeId": NODE_ID,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "queueDepth": self.queue.depth,
        }
        if extra:
            payload.update(extra)

        try:
            result = self.client.publish(topic, json.dumps(payload), qos=0)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as exc:
            log.warning("Heartbeat publish failed: %s", exc)
            return False

    def _send_command_ack(self, command_id: Optional[str], success: bool):
        """Send ACK/NACK for a received command."""
        if not command_id or not self.connected:
            return
        topic = f"sip/{NODE_ID}/command/ack" if success else f"sip/{NODE_ID}/command/nack"
        payload = {"commandId": command_id}
        self.client.publish(topic, json.dumps(payload), qos=0)

    def _replay_offline_queue(self):
        """Replay all queued incidents on reconnect."""
        items = self.queue.dequeue_all()
        if not items:
            return
        log.info("Replaying %d queued incidents", len(items))
        for item in items:
            try:
                result = self.client.publish(
                    item["topic"],
                    json.dumps(item["payload"]),
                    qos=item["qos"]
                )
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    self.queue.mark_sent(item["id"])
                    log.debug("Replayed incident id=%d", item["id"])
                else:
                    self.queue.mark_failed(item["id"])
            except Exception as exc:
                log.warning("Replay failed for id=%d: %s", item["id"], exc)
                self.queue.mark_failed(item["id"])


# ─── Singleton ─────────────────────────────────────────────────────────────────

_client: Optional[PiMqttClient] = None


def get_mqtt_client() -> PiMqttClient:
    global _client
    if _client is None:
        _client = PiMqttClient()
    return _client


def init_mqtt() -> PiMqttClient:
    client = get_mqtt_client()
    client.connect()
    return client