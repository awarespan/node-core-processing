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
from typing import Any, Callable, Dict, List, Optional

from shared.logging.logger import get_logger
from shared.models.events import ThreatEvent
from node_runtime.communications.mqtt_client import PiMqttClient, init_mqtt, get_mqtt_client
from node_runtime.communications.backend_sync import BackendSync, IncidentQueue, build_threat_event

log = get_logger("node_runtime.event_queue")


class EventQueueManager:
    """Coordinates resilient delivery of incidents and heartbeats."""

    def __init__(self, heartbeat_interval: int = 30, on_command: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.heartbeat_interval = heartbeat_interval
        self.on_command = on_command
        self.mqtt: Optional[PiMqttClient] = None
        self.backend: Optional[BackendSync] = None
        self.queue: Optional[IncidentQueue] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._last_cmd_poll = 0.0

    def _handle_command(self, cmd: Dict[str, Any]) -> None:
        cmd_id = cmd.get("commandId") or cmd.get("id")
        log.info("Received command via MQTT: %s", cmd_id)
        if self.on_command:
            try:
                self.on_command(cmd)
            except Exception as exc:
                log.error("Command handler error: %s", exc)
        if cmd_id and self.backend:
            self.backend.acknowledge_command(cmd_id)

    def start(self) -> None:
        """Initialize communication subsystems and start heartbeat/replay thread."""
        # Enroll first so MQTT topics and client identity use the backend-issued node ID.
        self.backend = BackendSync()
        self.mqtt = init_mqtt(on_command=self._handle_command)
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
        source_id: str = "builtin",
        event_id: Optional[str] = None,
        deterrence: Optional[Dict[str, Any]] = None,
        event: Optional[ThreatEvent] = None,
    ) -> None:
        """
        Handle a newly fired threat event:
        1. Attempt immediate delivery via MQTT.
        2. Fall back to REST API.
        3. Persist in SQLite offline queue if both fail.
        """
        if event is None:
            event = build_threat_event(
                tier=tier,
                labels=labels,
                confidence=confidence,
                model=model,
                action=action,
                latency_ms=latency_ms,
                frame_id=frame_id,
                source_id=source_id,
                event_id=event_id,
            )

        sent = False
        # 1. Authoritative REST API delivery to Central Backend
        if self.backend:
            rest_ok = self.backend.send_incident(event, model=model, deterrence=deterrence)
            if rest_ok:
                log.info("Incident %s synced via REST API to Central Backend", event.event_id)
                sent = True

        # 2. Real-time MQTT edge fanout
        if self.mqtt and self.mqtt.connected:
            mqtt_ok = self.mqtt.publish_incident(event, model=model, deterrence=deterrence)
            if mqtt_ok:
                log.info("Incident %s dispatched via MQTT", event.event_id)
                sent = True

        # 3. Durable offline SQLite queue if both fail
        if not sent and self.queue:
            self.queue.enqueue(event, model=model, metadata={"deterrence": deterrence or {}})
            log.warning("Incident %s stored in offline SQLite queue", event.event_id)

    def _worker_loop(self) -> None:
        """Periodic heartbeat, pending command polling, and offline queue replay loop."""
        last_heartbeat = 0.0
        while self._running:
            now = time.time()
            try:
                # 1. Command polling fallback: only if MQTT is disconnected, or every 60s
                is_mqtt_down = not (self.mqtt and self.mqtt.connected)
                poll_interval = 15.0 if is_mqtt_down else 60.0
                if now - self._last_cmd_poll >= poll_interval:
                    self._last_cmd_poll = now
                    self._poll_commands()

                # 2. Heartbeat every heartbeat_interval seconds
                if now - last_heartbeat >= self.heartbeat_interval:
                    last_heartbeat = now
                    self._send_heartbeat()
                    self._replay_offline_queue()
                    if self.queue:
                        self.queue.purge_old()
            except Exception as exc:
                log.warning("Worker loop iteration error: %s", exc)
            time.sleep(1.0)

    def _poll_commands(self) -> None:
        if not self.backend:
            return
        commands = self.backend.get_pending_commands()
        for cmd in commands:
            cmd_id = cmd.get("id")
            log.info("Processing pending REST command: %s (type=%s)", cmd_id, cmd.get("commandType"))
            if self.on_command:
                try:
                    self.on_command(cmd)
                except Exception as exc:
                    log.error("Command execution error for %s: %s", cmd_id, exc)
            if cmd_id:
                self.backend.acknowledge_command(cmd_id)

    def _send_heartbeat(self) -> None:
        depth = self.queue.depth if self.queue else 0
        extra = {"queueDepth": depth}

        if self.backend:
            self.backend.send_heartbeat(extra)

        if self.mqtt and self.mqtt.connected:
            self.mqtt.publish_heartbeat(extra)

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
                delivered = self.mqtt.publish_incident(event, model=model, deterrence=item.get("metadata", {}).get("deterrence", {}))

            if not delivered and self.backend:
                delivered = self.backend.send_incident(event, model=model, deterrence=item.get("metadata", {}).get("deterrence", {}))

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
