"""
AWARESPAN — Node Runtime Core
Module 2 Entry Point: Real-time sensor processing, edge inference, threat assessment, and deterrence.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import argparse
import asyncio
import base64
import json
import signal
import sys
import time
from collections import deque
from dataclasses import asdict
from typing import Deque, Dict, List, Optional, Tuple

import cv2
import numpy as np
import websockets

from shared.config.settings import get_settings
from shared.logging.logger import get_logger
from shared.models.events import Detection, ThreatEvent
from node_runtime.detection.visual.detector import VisualDetector
from node_runtime.processing.threat_assessment import ThreatAssessor, ThreatAssessment
from node_runtime.processing.response_selector import ResponseSelector
from node_runtime.deterrence.siren import DeterrenceController
from node_runtime.communications.event_queue import EventQueueManager

log = get_logger("node_runtime.core")


class RuntimeCore:
    """Manages edge inference, streaming broadcast, and threat deterrence."""

    def __init__(self, detector: VisualDetector, assessor: ThreatAssessor):
        self.settings = get_settings()
        self.detector = detector
        self.assessor = assessor
        self.response_selector = ResponseSelector(siren_enabled=self.settings.siren_enabled)
        self.deterrence = DeterrenceController(
            siren_file=self.settings.siren_file,
            enabled=self.settings.siren_enabled,
            cooldown_sec=self.settings.cooldown_seconds,
        )
        self.event_queue: Optional[EventQueueManager] = None

        self.dashboard_clients: set = set()
        self.frame_queue: asyncio.Queue = asyncio.Queue(maxsize=3)
        self.logs: Deque[ThreatEvent] = deque(maxlen=200)

        self.latest_frame_message: Optional[str] = None
        self.last_event_ms = 0
        self.frame_counter = 0
        self.fps_window_start = time.time()
        self.current_fps = 0

    async def route_connection(self, websocket):
        """Route connection based on path."""
        path = "/"
        if hasattr(websocket, "request") and hasattr(websocket.request, "path"):
            path = websocket.request.path

        if path == "/health":
            # Simple HTTP-level health response over WebSocket connection
            await websocket.send(json.dumps({"status": "ok", "node": self.settings.node_id}))
            await websocket.close()
            return
        elif path == "/ingest":
            await self._ingest_handler(websocket)
        else:
            await self._dashboard_handler(websocket)

    async def _ingest_handler(self, websocket):
        """Ingests raw camera/laptop frames."""
        log.info("Frame ingestion client connected")
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    continue
                if data.get("type") == "frame":
                    self._enqueue_frame(data)
        except Exception as exc:
            log.debug("Ingestion connection ended: %s", exc)
        finally:
            log.info("Frame ingestion client disconnected")

    async def _dashboard_handler(self, websocket):
        """Broadcasts annotated frames and incident logs to dashboard clients."""
        self.dashboard_clients.add(websocket)
        log.info("Dashboard client connected (active clients: %d)", len(self.dashboard_clients))
        try:
            if self.latest_frame_message:
                await websocket.send(self.latest_frame_message)
            for event in list(self.logs)[-20:]:
                await websocket.send(json.dumps({"type": "log", "event": event.to_dict()}, separators=(",", ":")))
            async for _ in websocket:
                pass
        except Exception as exc:
            log.debug("Dashboard connection closed: %s", exc)
        finally:
            self.dashboard_clients.discard(websocket)

    def _enqueue_frame(self, packet: Dict) -> None:
        if self.frame_queue.full():
            try:
                self.frame_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        self.frame_queue.put_nowait(packet)

    async def processor_loop(self) -> None:
        """Main inference and threat assessment loop."""
        log.info("Node Runtime processor loop active")
        while True:
            packet = await self.frame_queue.get()
            frame_id = int(packet.get("frame_id", 0))
            source_ts_ms = int(packet.get("ts_ms", 0))
            jpeg_b64 = packet.get("jpeg_b64", "")

            try:
                frame = self._decode_frame(jpeg_b64)
            except Exception as exc:
                log.warning("Frame decode failed: %s", exc)
                continue

            # Run inference
            annotated, detections = self.detector.infer(frame)
            assessment: ThreatAssessment = self.assessor.evaluate(detections)

            now_ms = int(time.time() * 1000)
            latency_ms = now_ms - source_ts_ms if source_ts_ms else 0

            self.frame_counter += 1
            self._update_fps()

            if assessment.tier != "none" and self._cooldown_passed(now_ms):
                actions = self.response_selector.select_response(assessment)

                # Audio deterrence
                action_str = "alert"
                if actions.get("siren"):
                    if self.deterrence.trigger_siren(assessment.labels):
                        action_str = "siren"

                event = ThreatEvent(
                    event_id=f"evt-{now_ms}",
                    ts_ms=now_ms,
                    tier=assessment.tier,
                    labels=assessment.labels,
                    max_confidence=assessment.max_confidence,
                    action=action_str,
                    latency_ms=latency_ms,
                    frame_id=frame_id,
                    model=getattr(self.detector, "model_path", ""),
                )

                self.logs.append(event)
                await self._broadcast({"type": "log", "event": event.to_dict()})
                self.last_event_ms = now_ms

                # Transmit event to cloud / MQTT / SQLite queue
                if self.event_queue:
                    self.event_queue.enqueue_event(
                        tier=assessment.tier,
                        labels=assessment.labels,
                        confidence=assessment.max_confidence,
                        model=getattr(self.detector, "model_path", ""),
                        action=action_str,
                        latency_ms=latency_ms,
                        frame_id=frame_id,
                    )

            # Build and broadcast annotated frame
            try:
                frame_msg = self._build_frame_message(annotated, latency_ms, frame_id)
                self.latest_frame_message = frame_msg
                await self._broadcast_raw(frame_msg)
            except Exception as exc:
                log.warning("Failed to broadcast annotated frame: %s", exc)

    def _decode_frame(self, jpeg_b64: str) -> np.ndarray:
        jpeg_bytes = base64.b64decode(jpeg_b64)
        data = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("Empty frame")
        return frame

    def _cooldown_passed(self, now_ms: int) -> bool:
        return (now_ms - self.last_event_ms) >= int(self.settings.cooldown_seconds * 1000)

    def _update_fps(self) -> None:
        window = time.time() - self.fps_window_start
        if window >= 1.0:
            self.current_fps = int(self.frame_counter / window)
            self.frame_counter = 0
            self.fps_window_start = time.time()

    def _build_frame_message(self, frame, latency_ms: int, frame_id: int) -> str:
        ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        if not ok:
            raise RuntimeError("Failed to encode frame")
        b64 = base64.b64encode(buffer).decode("ascii")
        payload = {
            "type": "frame",
            "frame_id": frame_id,
            "annotated_b64": b64,
            "latency_ms": latency_ms,
            "fps": self.current_fps,
        }
        return json.dumps(payload, separators=(",", ":"))

    async def _broadcast(self, payload: Dict) -> None:
        msg = json.dumps(payload, separators=(",", ":"))
        await self._broadcast_raw(msg)

    async def _broadcast_raw(self, message: str) -> None:
        if not self.dashboard_clients:
            return
        to_remove = []
        coros = [client.send(message) for client in self.dashboard_clients]
        results = await asyncio.gather(*coros, return_exceptions=True)
        for client, res in zip(list(self.dashboard_clients), results):
            if isinstance(res, Exception):
                to_remove.append(client)
        for client in to_remove:
            self.dashboard_clients.discard(client)


async def run_server(args: argparse.Namespace) -> None:
    settings = get_settings()
    detector = VisualDetector(
        model_path=args.model or settings.default_model,
        imgsz=args.imgsz,
        confidence=args.conf or settings.confidence_threshold,
    )
    assessor = ThreatAssessor()
    core = RuntimeCore(detector, assessor)

    # Initialize communications
    eq = EventQueueManager(heartbeat_interval=30)
    eq.start()
    core.event_queue = eq

    host = args.host or settings.runtime_host
    port = args.port or settings.runtime_port

    async with websockets.serve(
        core.route_connection,
        host,
        port,
        max_size=2**24,
        ping_interval=20,
        ping_timeout=20,
    ):
        log.info("AWARESPAN Node Runtime active on ws://%s:%d (ingest: /ingest, dashboard: /)", host, port)
        try:
            await core.processor_loop()
        finally:
            eq.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="AWARESPAN Node Runtime Server")
    parser.add_argument("--host", default=None, help="Bind address")
    parser.add_argument("--port", type=int, default=None, help="WebSocket port")
    parser.add_argument("--model", default=None, help="YOLOv8 weights path")
    parser.add_argument("--imgsz", type=int, default=640, help="Inference resolution")
    parser.add_argument("--conf", type=float, default=None, help="Confidence threshold")
    args = parser.parse_args()

    try:
        asyncio.run(run_server(args))
    except KeyboardInterrupt:
        log.info("Node Runtime terminated by operator signal.")


if __name__ == "__main__":
    main()
