#!/usr/bin/env python3
"""
Backend sync module for SIP Pi.

Provides:
- Incident ingestion (idempotent, queued offline when disconnected)
- Command reception (via MQTT)
- Heartbeat emission
- Threat event forwarding to backend REST API

The Pi connects OUT to the MQTT broker — the backend never needs to reach the Pi's IP.
"""

import asyncio
import json
import logging
import os
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import dotenv
import requests

log = logging.getLogger("backend_sync")

# ─── Canonical environment resolution ────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def find_canonical_env():
    """Locate canonical root .env with explicit repository-root resolution."""
    candidates = [
        os.path.join(SCRIPT_DIR, "..", ".env"),
        os.path.join(SCRIPT_DIR, ".env"),
        os.path.join(os.path.expanduser("~"), "edge-ai", ".env"),
        os.path.join(os.path.expanduser("~"), "SIP", "node-backend", ".env"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return os.path.abspath(candidate)
    return None

_env_path = find_canonical_env()
if _env_path:
    dotenv.load_dotenv(_env_path)

NODE_ID = os.getenv("PI_NODE_ID", "sip-pi-001")
DEVICE_SECRET = os.getenv("PI_DEVICE_SECRET", "changeme")
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8080").rstrip("/")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (X11; Linux aarch64) SIP-Edge-Node/1.0"
}
if BACKEND_API_KEY:
    HEADERS["X-API-Key"] = BACKEND_API_KEY


# ─── Backend REST Sync ─────────────────────────────────────────────────────────

class BackendSync:
    """
    REST-based sync with the backend.
    Falls back gracefully when offline.
    """

    def __init__(self, api_url: str = BACKEND_API_URL, api_key: str = BACKEND_API_KEY):
        self.api_url = api_url
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux aarch64) SIP-Edge-Node/1.0"
        }
        if api_key:
            self.headers["X-API-Key"] = api_key

    def _post(self, path: str, payload: Dict) -> Optional[Dict]:
        if not self.api_url:
            return None
        try:
            resp = requests.post(
                f"{self.api_url}{path}",
                json=payload,
                headers=self.headers,
                timeout=5,
            )
            if resp.ok:
                return resp.json() if resp.content else {}
            log.debug("Backend POST %s -> %d", path, resp.status_code)
        except requests.RequestException as exc:
            log.warning("Backend unreachable at %s: %s", self.api_url, exc)
        return None

    def _get(self, path: str, params: Optional[Dict] = None) -> Optional[Dict]:
        if not self.api_url or self.api_url == "http://localhost:8080":
            return None
        try:
            resp = requests.get(
                f"{self.api_url}{path}",
                params=params or {},
                headers=self.headers,
                timeout=5,
            )
            if resp.ok:
                return resp.json()
        except requests.RequestException as exc:
            log.debug("Backend GET %s -> %s", path, exc)
        return None

    def send_incident(self, incident: Dict) -> bool:
        """POST an incident to the backend REST API."""
        result = self._post("/api/v1/incidents", incident)
        return result is not None

    def send_heartbeat(self, heartbeat: Dict) -> bool:
        """POST a heartbeat."""
        result = self._post(f"/api/v1/nodes/{NODE_ID}/heartbeat", heartbeat)
        return result is not None

    def get_pending_commands(self) -> List[Dict]:
        """Fetch pending commands from backend."""
        result = self._get(f"/api/v1/commands/pending/{NODE_ID}")
        if result and isinstance(result, list):
            return result
        return []

    def ack_command(self, command_id: str) -> bool:
        result = self._post(f"/api/v1/commands/{command_id}/acknowledge", {})
        return result is not None


# ─── Threat Event Builder ──────────────────────────────────────────────────────

@dataclass
class ThreatEvent:
    """Canonical threat event format sent to backend."""
    incident_id: str = field(default_factory=lambda: f"inc-{uuid.uuid4().hex[:12]}")
    idempotency_key: str = ""
    node_id: str = NODE_ID
    detection_time: str = ""
    threat_type: str = "UNKNOWN"
    threat_severity: str = "LOW"
    threat_description: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_readable: str = ""
    location_accuracy: Optional[float] = None
    model_version: str = ""
    confidence: float = 0.0
    detections: List[Dict[str, Any]] = field(default_factory=list)
    tier: int = 0
    detection_domain: str = "UNKNOWN"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if not d["idempotency_key"]:
            d["idempotency_key"] = f"{NODE_ID}-{self.incident_id}"
        if not d["detection_time"]:
            d["detection_time"] = datetime.utcnow().isoformat() + "Z"
        return d

    def to_mqtt_payload(self) -> Dict[str, Any]:
        """Format for MQTT pub to sip/{nodeId}/incidents."""
        return {
            "incidentId": self.incident_id,
            "idempotencyKey": self.to_dict()["idempotency_key"],
            "nodeId": self.node_id,
            "detectionTime": self.to_dict()["detection_time"],
            "threatType": self.threat_type,
            "threatSeverity": self.threatSeverity_to_backend(self.threat_severity),
            "threatDescription": self.threat_description,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "locationReadable": self.location_readable,
            "locationAccuracy": self.location_accuracy,
            "modelVersion": self.model_version,
            "confidence": self.confidence,
            "detections": self.detections,
            "tier": self.tier,
            "detectionDomain": self.detection_domain,
            "syncStatus": "PENDING",
        }

    @staticmethod
    def threat_severity_to_backend(severity: str) -> str:
        """Convert edge-server severity labels to backend enum."""
        mapping = {
            "LOW": "LOW",
            "MEDIUM": "MEDIUM",
            "HIGH": "HIGH",
            "tier1": "LOW",
            "tier2": "HIGH",
            "NON_DETERRABLE": "NON_DETERRABLE",
        }
        return mapping.get(severity, "LOW")


# ─── Offline Incident Queue ────────────────────────────────────────────────────

class IncidentQueue:
    """
    SQLite-based offline queue for incidents.
    When both MQTT and REST backend are unavailable, incidents are persisted locally.
    Replayed on reconnect.
    """

    def __init__(self, db_path: str = "/tmp/sip_incident_queue.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_attempt REAL,
                    sent_via TEXT DEFAULT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at ON incidents(created_at)
            """)

    def enqueue(self, event: ThreatEvent, via: str = "mqtt"):
        payload = json.dumps(event.to_dict())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO incidents (event_json, created_at, sent_via) VALUES (?, ?, ?)",
                (payload, time.time(), via)
            )

    def dequeue_all(self) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, event_json, sent_via FROM incidents ORDER BY created_at ASC"
            ).fetchall()
        return [{"id": r[0], "event": json.loads(r[1]), "via": r[2]} for r in rows]

    def mark_sent(self, row_id: int, via: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE incidents SET attempts = attempts + 1, last_attempt = ?, sent_via = ? WHERE id = ?",
                (time.time(), via, row_id)
            )

    def purge_old(self, max_age_hours: int = 48, max_attempts: int = 20):
        cutoff = time.time() - max_age_hours * 3600
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM incidents WHERE created_at < ? OR attempts > ?",
                (cutoff, max_attempts)
            )

    @property
    def depth(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]


# ─── Pi Integration ────────────────────────────────────────────────────────────

def build_threat_event(
    tier: str,
    labels: List[str],
    confidence: float,
    model_version: str = "",
) -> ThreatEvent:
    """Build a ThreatEvent from edge_server.py detection data."""
    severity_map = {"tier1": "LOW", "tier2": "HIGH"}
    # Map detection labels to backend threat types
    weapon_labels = {"knife", "gun", "weapon"}
    animal_labels = {"dog", "cat", "horse", "cow", "sheep", "elephant", "bear", "zebra", "giraffe"}
    violence_labels = {"person"}

    detected_labels = {l.lower() for l in labels}
    threat_domain = "UNKNOWN"
    if detected_labels & weapon_labels:
        threat_domain = "WEAPON"
    elif detected_labels & animal_labels:
        threat_domain = "ANIMAL"
    elif detected_labels & violence_labels:
        threat_domain = "VIOLENCE"

    event = ThreatEvent(
        incident_id=f"inc-{uuid.uuid4().hex[:12]}",
        node_id=NODE_ID,
        detection_time=datetime.utcnow().isoformat() + "Z",
        threat_type=",".join(sorted(labels)) if labels else "UNKNOWN",
        threat_severity=severity_map.get(tier, "LOW"),
        model_version=model_version,
        confidence=confidence,
        detections=[{"label": l, "confidence": confidence} for l in labels],
        tier=2 if tier == "tier2" else 1,
        detection_domain=threat_domain,
    )
    return event


# ─── Health check ──────────────────────────────────────────────────────────────

def check_backend_health() -> bool:
    """Check if the backend REST API is reachable."""
    if not BACKEND_API_URL or BACKEND_API_URL == "http://localhost:8080":
        return False
    try:
        resp = requests.get(f"{BACKEND_API_URL}/actuator/health", timeout=3)
        return resp.ok
    except requests.RequestException:
        return False