"""
AWARESPAN — Backend REST Sync & Offline SQLite Queue
Handles REST incident delivery, heartbeats, and durable offline incident persistence.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import json
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from shared.config.settings import get_settings
from shared.logging.logger import get_logger
from shared.models.events import ThreatEvent

log = get_logger("node_runtime.backend_sync")


def build_threat_event(
    tier: str,
    labels: List[str],
    confidence: float,
    model: str = "",
    action: str = "alert",
    latency_ms: int = 0,
    frame_id: int = 0,
    source_id: str = "builtin",
) -> ThreatEvent:
    """Build a standard ThreatEvent instance."""
    now_ms = int(time.time() * 1000)
    return ThreatEvent(
        event_id=f"evt-{now_ms}-{uuid.uuid4().hex[:6]}",
        ts_ms=now_ms,
        tier=tier,
        labels=labels,
        max_confidence=confidence,
        action=action,
        latency_ms=latency_ms,
        frame_id=frame_id,
        model=model,
        source_id=source_id,
    )


# ─── SQLite Offline Incident Queue ──────────────────────────────────────────

class IncidentQueue:
    """
    Durable offline queue backed by SQLite.
    Stores incidents when network / MQTT is down, and safely replays upon recovery.
    """

    def __init__(self, db_path: Optional[str] = None):
        settings = get_settings()
        self.db_path = db_path or settings.offline_queue_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS incident_queue (
                        id TEXT PRIMARY KEY,
                        event_json TEXT NOT NULL,
                        model TEXT NOT NULL,
                        attempts INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL,
                        last_attempt_at TEXT,
                        status TEXT DEFAULT 'pending'
                    )
                """)
                conn.commit()
        except Exception as exc:
            log.error("Failed to initialize SQLite incident queue at %s: %s", self.db_path, exc)

    def enqueue(self, event: ThreatEvent, model: str = "") -> None:
        """Enqueue an incident for deferred delivery."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO incident_queue (id, event_json, model, attempts, created_at, status)
                    VALUES (?, ?, ?, 0, ?, 'pending')
                    """,
                    (
                        event.event_id,
                        json.dumps(event.to_dict()),
                        model,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                conn.commit()
            log.info("Incident %s enqueued to offline storage (depth=%d)", event.event_id, self.depth)
        except Exception as exc:
            log.error("Failed to enqueue incident %s: %s", event.event_id, exc)

    def dequeue_all(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch pending queued items ordered by creation time."""
        items = []
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT id, event_json, model, attempts FROM incident_queue
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT ?
                    """,
                    (limit,),
                )
                for row in cursor.fetchall():
                    try:
                        data = json.loads(row["event_json"])
                        event = ThreatEvent(
                            event_id=data["event_id"],
                            ts_ms=data["ts_ms"],
                            tier=data["tier"],
                            labels=data["labels"],
                            max_confidence=data["max_confidence"],
                            action=data["action"],
                            latency_ms=data.get("latency_ms", 0),
                            frame_id=data.get("frame_id", 0),
                            model=data.get("model", row["model"]),
                            source_id=data.get("source_id", "builtin"),
                        )
                        items.append({
                            "id": row["id"],
                            "event": event,
                            "model": row["model"],
                            "attempts": row["attempts"],
                        })
                    except Exception as err:
                        log.warning("Corrupt event in queue (id=%s): %s", row["id"], err)
        except Exception as exc:
            log.warning("Failed to dequeue from incident queue: %s", exc)
        return items

    get_pending = dequeue_all

    def mark_success(self, event_id: str) -> None:
        """Remove successfully delivered incident from queue."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM incident_queue WHERE id = ?", (event_id,))
                conn.commit()
            log.debug("Queue item %s delivered and purged", event_id)
        except Exception as exc:
            log.warning("Failed to remove delivered item %s: %s", event_id, exc)

    def mark_failure(self, event_id: str) -> None:
        """Increment attempt count and update last attempted timestamp."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE incident_queue
                    SET attempts = attempts + 1, last_attempt_at = ?
                    WHERE id = ?
                    """,
                    (datetime.now(timezone.utc).isoformat(), event_id),
                )
                conn.commit()
        except Exception as exc:
            log.warning("Failed to mark failure for item %s: %s", event_id, exc)

    def purge_old(self, max_age_hours: int = 48, max_attempts: int = 25) -> int:
        """Purge obsolete or permanently failing queue entries."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    DELETE FROM incident_queue
                    WHERE attempts >= ?
                    """,
                    (max_attempts,),
                )
                deleted = cursor.rowcount
                conn.commit()
                return deleted
        except Exception:
            return 0

    @property
    def depth(self) -> int:
        """Count pending queued items."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM incident_queue WHERE status = 'pending'")
                row = cursor.fetchone()
                return row[0] if row else 0
        except Exception:
            return 0


# ─── REST Backend Sync ───────────────────────────────────────────────────────

class BackendSync:
    """REST synchronization with AWARESPAN central API."""

    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None):
        settings = get_settings()
        self.api_url = (api_url or settings.backend_api_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.backend_api_key
        self.node_id = settings.node_id
        self.device_secret = settings.device_secret

        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "AWARESPAN-Edge-Node/2.0",
            "X-Node-Id": self.node_id,
            "X-Device-Secret": self.device_secret,
        }
        if self.api_key:
            self.headers["X-API-Key"] = self.api_key

    def send_incident(self, event: ThreatEvent, model: str = "") -> bool:
        """Transmit incident to backend REST endpoint /api/v1/incidents."""
        if not self.api_url:
            log.debug("BACKEND_API_URL not configured; skipping REST incident sync.")
            return False
        url = f"{self.api_url}/api/v1/incidents"
        threat_type = event.labels[0].upper() if event.labels else "UNKNOWN"
        detection_time = datetime.fromtimestamp(event.ts_ms / 1000.0, timezone.utc).isoformat()
        threat_desc = (
            f"Detected {', '.join(event.labels)} ({event.max_confidence * 100:.1f}%)"
            if event.labels
            else "Threat detected"
        )
        threat_severity = (
            "CRITICAL"
            if event.tier in ("tier1", "critical")
            else "HIGH"
            if event.tier in ("tier2", "high")
            else "MEDIUM"
        )

        payload = {
            "incidentId": event.event_id,
            "idempotencyKey": event.event_id,
            "nodeId": self.node_id,
            "threatType": threat_type,
            "threatSeverity": threat_severity,
            "threatDescription": threat_desc,
            "confidence": float(event.max_confidence),
            "detectionTime": detection_time,
            "tier": 1 if event.tier in ("tier1", "critical") else 2,
        }
        try:
            res = requests.post(url, json=payload, headers=self.headers, timeout=5)
            if res.status_code in (200, 201):
                log.info("Incident %s synced via REST API (status %d)", event.event_id, res.status_code)
                return True
            log.warning("REST incident sync failed (status %d): %s", res.status_code, res.text[:200])
            return False
        except Exception as exc:
            log.debug("REST incident sync exception (offline): %s", exc)
            return False

    def send_heartbeat(self, extra: Optional[Dict[str, Any]] = None) -> bool:
        """Transmit heartbeat to backend REST endpoint /api/v1/nodes/{nodeId}/heartbeat."""
        if not self.api_url:
            return False
        url = f"{self.api_url}/api/v1/nodes/{self.node_id}/heartbeat"
        now_iso = datetime.now(timezone.utc).isoformat()
        payload = {
            "nodeId": self.node_id,
            "status": "ONLINE",
            "timestamp": now_iso,
            **(extra or {}),
        }
        try:
            res = requests.post(url, json=payload, headers=self.headers, timeout=4)
            if res.status_code in (200, 201):
                log.debug("Heartbeat transmitted successfully for %s", self.node_id)
                return True
            log.warning("Heartbeat transmission failed (%d): %s", res.status_code, res.text[:200])
            return False
        except Exception as exc:
            log.debug("Heartbeat transmission exception: %s", exc)
            return False
