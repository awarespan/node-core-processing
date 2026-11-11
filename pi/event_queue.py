#!/usr/bin/env python3
"""
Event queue integration for SIP edge_server.py.

Wires the MQTT client and backend sync into the existing EdgeCore threat events.
When a ThreatEvent fires in edge_server, this module:
1. Sends it via MQTT to sip/{nodeId}/incidents
2. Falls back to REST API if MQTT is disconnected
3. Queues it in SQLite if both are down
4. Replays queued events on reconnect
"""

import asyncio
import logging
import threading
import time
from typing import List, Optional

from mqtt_client import get_mqtt_client, init_mqtt, PiMqttClient
from backend_sync import (
    BackendSync,
    IncidentQueue,
    ThreatEvent,
    build_threat_event,
    NODE_ID,
)

log = logging.getLogger("event_queue")

# Singleton instances
_mqtt_client: Optional[PiMqttClient] = None
_backend_sync: Optional[BackendSync] = None
_incident_queue: Optional[IncidentQueue] = None
_heartbeat_thread: Optional[threading.Thread] = None
_running = False


def start(heartbeat_interval: int = 30) -> None:
    """
    Initialize MQTT client and backend sync.
    Starts background heartbeat thread.
    """
    global _mqtt_client, _backend_sync, _incident_queue, _running

    _mqtt_client = init_mqtt()
    _backend_sync = BackendSync()
    _incident_queue = IncidentQueue()
    _running = True

    # Start heartbeat thread
    _heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(heartbeat_interval,),
        daemon=True,
    )
    _heartbeat_thread.start()

    log.info("Event queue started (MQTT connected=%s, queue_depth=%d)",
             _mqtt_client.connected, _incident_queue.depth)


def stop() -> None:
    global _running
    _running = False
    if _mqtt_client:
        _mqtt_client.disconnect()


def _heartbeat_loop(interval: int) -> None:
    """Background thread: sends heartbeats and replays queue periodically."""
    while _running:
        time.sleep(interval)
        try:
            _send_heartbeat()
            _replay_queue()
            if _incident_queue:
                _incident_queue.purge_old(max_age_hours=48, max_attempts=20)
        except Exception as exc:
            log.warning("Heartbeat/replay loop error: %s", exc)


def _send_heartbeat() -> None:
    if not _mqtt_client:
        return
    extra = {}
    if _incident_queue:
        extra["queueDepth"] = _incident_queue.depth
    _mqtt_client.publish_heartbeat(extra)


def _replay_queue() -> None:
    """Replay queued incidents via REST API (fallback when MQTT disconnected)."""
    if not _incident_queue or not _backend_sync:
        return
    items = _incident_queue.dequeue_all()
    for item in items:
        event: ThreatEvent = item["event"]
        via = "rest"
        # Try MQTT first if connected
        if _mqtt_client and _mqtt_client.connected:
            payload = event.to_mqtt_payload()
            # Create a mock incident-like dict for REST fallback
            incident_dict = event.to_dict()
            success = _mqtt_client.publish_incident(incident_dict)
            if not success:
                # MQTT publish failed (queued internally)
                via = "mqtt_offline"
        else:
            # MQTT not connected — try REST
            success = _backend_sync.send_incident(event.to_dict())
            if not success:
                # Re-enqueue for next attempt — DO NOT mark sent
                _incident_queue.enqueue(event, via="rest")
                via = "rest_failed"
            else:
                _incident_queue.mark_sent(item["id"], via)


def enqueue_event(
    tier: str,
    labels: List[str],
    confidence: float,
    model_version: str = "",
) -> bool:
    """
    Called from edge_server.py when a threat event fires.
    Attempts MQTT first, falls back to REST, queues if both fail.
    """
    # Lazy init — ensures queue is ready even if start() was never called
    if not _incident_queue or not _backend_sync:
        log.warning("Event queue not yet initialized — initializing now")
        start()

    event = build_threat_event(tier, labels, confidence, model_version)

    # Attempt MQTT publish
    if _mqtt_client and _mqtt_client.connected:
        payload = event.to_mqtt_payload()
        incident_dict = event.to_dict()
        mqtt_ok = _mqtt_client.publish_incident(incident_dict)
        if mqtt_ok:
            log.info("Threat event %s sent via MQTT (tier=%s, labels=%s)",
                     event.incident_id, tier, labels)
            return True

    # Fallback: REST API
    rest_ok = _backend_sync.send_incident(event.to_dict())
    if rest_ok:
        log.info("Threat event %s sent via REST (tier=%s, labels=%s)",
                 event.incident_id, tier, labels)
        return True

    # Both failed — queue for replay
    _incident_queue.enqueue(event, via="mqtt_failed")
    log.info("Threat event %s queued offline (queue depth=%d)",
             event.incident_id, _incident_queue.depth)
    return False


def set_command_callback(callback) -> None:
    """Register a callback for incoming commands from the backend."""
    if _mqtt_client:
        _mqtt_client.set_command_callback(callback)


def get_queue_depth() -> int:
    return _incident_queue.depth if _incident_queue else 0


def is_mqtt_connected() -> bool:
    return _mqtt_client.connected if _mqtt_client else False