"""
AWARESPAN — Event Queue Manager
Coordinates MQTT dispatch, REST fallback, offline queue persistence, and automatic replay.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import logging
import threading
import time
from typing import Dict, List, Optional

from shared.logging.logger import get_logger
from shared.models.events import ThreatEvent
from node_runtime.communications.mqtt_client import PiMqttClient, init_mqtt, get_mqtt_client
from node_runtime.communications.backend_sync import BackendSync, IncidentQueue, build_threat_event

log = get_logger("node_runtime.event_queue")


class EventQueueManager:
    """Coordinates resilient delivery of incidents and heartbeats."""

    def __init__(self, heartbeat_interval: int = 30):
        self.heartbeat_interval = heartbeat_interval
        self.mqtt: Optional[PiMqttClient] = None
        self.backend: Optional[BackendSync] = None
        self.queue: Optional[IncidentQueue] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        """Initialize communication subsystems and start heartbeat/replay thread."""
        self.mqtt = init_mqtt()
        self.backend = BackendSync()
        self.queue = IncidentQueue()
        self._running = True

        self._thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="awarespan-event-queue",
        )
        self._thread.start()
        log.info("Event queue manager started (MQTT connected: %s, queue depth: %d)", self.mqtt.connected, self.queue.depth)

    def stop(self) -> None:
        """Stop background worker and disconnect MQTT."""
        self._running = False
        if self.mqtt:
            self.mqtt.disconnect()
        log.info("Event queue manager stopped.")

    def enqueue_event(
        self,
        tier: str,
        labels: List[str],
        confidence: float,
        model: str = "",
        action: str = "alert",
        latency_ms: int = 0,
        frame_id: int = 0,
    ) -> None:
        """
        Handle a newly fired threat event:
        1. Attempt immediate delivery via MQTT.
        2. Fall back to REST API.
        3. Persist in SQLite offline queue if both fail.
        """
        event = build_threat_event(
            tier=tier,
            labels=labels,
            confidence=confidence,
            model=model,
            action=action,
            latency_ms=latency_ms,
            frame_id=frame_id,
        )

        sent = False
        # 1. Try MQTT
        if self.mqtt and self.mqtt.connected:
            sent = self.mqtt.publish_incident(event, model=model)
            if sent:
                log.info("Incident %s dispatched via MQTT", event.event_id)

        # 2. Try REST API fallback
        if not sent and self.backend:
            sent = self.backend.send_incident(event, model=model)
            if sent:
                log.info("Incident %s dispatched via REST API fallback", event.event_id)

        # 3. Queue offline
        if not sent and self.queue:
            self.queue.enqueue(event, model=model)
            log.warning("Incident %s stored in offline SQLite queue", event.event_id)

    def _worker_loop(self) -> None:
        """Periodic heartbeat and offline queue replay loop."""
        while self._running:
            time.sleep(self.heartbeat_interval)
            try:
                self._send_heartbeat()
                self._replay_offline_queue()
                if self.queue:
                    self.queue.purge_old()
            except Exception as exc:
                log.warning("Heartbeat/replay loop error: %s", exc)

    def _send_heartbeat(self) -> None:
        depth = self.queue.depth if self.queue else 0
        extra = {"queueDepth": depth}

        sent = False
        if self.mqtt and self.mqtt.connected:
            sent = self.mqtt.publish_heartbeat(extra)

        if not sent and self.backend:
            self.backend.send_heartbeat(extra)

    def _replay_offline_queue(self) -> None:
        """Replay queued incidents when network is available."""
        if not self.queue or self.queue.depth == 0:
            return

        items = self.queue.dequeue_all(limit=25)
        for item in items:
            event: ThreatEvent = item["event"]
            model: str = item["model"]
            delivered = False

            if self.mqtt and self.mqtt.connected:
                delivered = self.mqtt.publish_incident(event, model=model)

            if not delivered and self.backend:
                delivered = self.backend.send_incident(event, model=model)

            if delivered:
                self.queue.mark_success(item["id"])
            else:
                self.queue.mark_failure(item["id"])
                # Break to avoid hammering disconnected endpoint
                break


# Global module singleton functions for compatibility
_global_eq: Optional[EventQueueManager] = None


def start_event_queue(interval: int = 30) -> EventQueueManager:
    global _global_eq
    if _global_eq is None:
        _global_eq = EventQueueManager(heartbeat_interval=interval)
        _global_eq.start()
    return _global_eq


def stop_event_queue() -> None:
    global _global_eq
    if _global_eq:
        _global_eq.stop()
        _global_eq = None


def enqueue_event(*args, **kwargs) -> None:
    if _global_eq:
        _global_eq.enqueue_event(*args, **kwargs)
