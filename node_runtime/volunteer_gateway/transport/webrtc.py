"""
AWARESPAN — WebRTC Peer Connection & Media Track Handler
Provides sub-second latency video and audio ingestion via WebRTC with STUN/TURN NAT traversal.
Gracefully falls back to binary WebSocket when WebRTC is not supported or unavailable.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional

try:
    import cv2
except ImportError:
    cv2 = None

from shared.config.settings import get_settings
from shared.logging.logger import get_logger
from node_runtime.media.routing.media_router import CoreMediaRouter, get_media_router

log = get_logger("volunteer_gateway.webrtc")

# Gracefully import aiortc
try:
    import av
    from aiortc import (
        RTCConfiguration,
        RTCIceCandidate,
        RTCIceServer,
        RTCPeerConnection,
        RTCSessionDescription,
    )
    from aiortc.sdp import candidate_from_sdp
    AIORTC_AVAILABLE = True
except (ImportError, Exception) as _import_err:
    AIORTC_AVAILABLE = False
    log.info("WebRTC (aiortc/av) not available in current environment: %s. Relying on binary WebSocket.", _import_err)


def is_webrtc_supported() -> bool:
    """Return True if aiortc and av are installed and available."""
    return AIORTC_AVAILABLE


class WebRTCPeerSession:
    """
    Manages WebRTC PeerConnection for an active volunteer camera/microphone stream.
    Decodes inbound RTP H.264/VP8 video tracks and Opus audio tracks into CoreMediaRouter.
    """

    def __init__(
        self,
        source_id: str,
        session_id: str,
        router: Optional[CoreMediaRouter] = None,
        on_close: Optional[Callable[[str], None]] = None,
    ):
        self.source_id = source_id
        self.session_id = session_id
        self.router = router or get_media_router()
        self.on_close_cb = on_close
        self.settings = get_settings()

        self.pc: Optional[Any] = None
        self._closed = False
        self._tasks: List[asyncio.Task] = []
        self._frame_seq = 0

    def _build_rtc_configuration(self) -> Any:
        if not AIORTC_AVAILABLE:
            return None

        ice_servers = []
        # STUN servers
        for stun_url in getattr(self.settings, "stun_servers", []):
            if stun_url:
                ice_servers.append(RTCIceServer(urls=stun_url))

        # Optional TURN server
        turn_url = getattr(self.settings, "turn_url", "").strip()
        if turn_url:
            turn_user = getattr(self.settings, "turn_username", "")
            turn_pass = getattr(self.settings, "turn_password", "")
            ice_servers.append(
                RTCIceServer(
                    urls=turn_url,
                    username=turn_user,
                    credential=turn_pass,
                )
            )

        return RTCConfiguration(iceServers=ice_servers)

    async def handle_offer(self, sdp: str, sdp_type: str = "offer") -> Dict[str, str]:
        """
        Processes client WebRTC SDP offer, sets up incoming track consumers,
        and generates SDP answer.
        """
        if not AIORTC_AVAILABLE:
            raise RuntimeError("WebRTC streaming not available: aiortc/av dependencies missing")

        config = self._build_rtc_configuration()
        self.pc = RTCPeerConnection(configuration=config)

        @self.pc.on("track")
        def on_track(track):
            log.info("Received WebRTC media track: %s (%s) for source %s", track.kind, track.id, self.source_id)
            if track.kind == "video":
                task = asyncio.create_task(self._consume_video_track(track))
                self._tasks.append(task)
            elif track.kind == "audio":
                task = asyncio.create_task(self._consume_audio_track(track))
                self._tasks.append(task)

        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            log.info("WebRTC connection state for source %s: %s", self.source_id, self.pc.connectionState)
            if self.pc.connectionState in ("failed", "closed"):
                await self.close()

        offer = RTCSessionDescription(sdp=sdp, type=sdp_type)
        await self.pc.setRemoteDescription(offer)

        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)

        return {
            "sdp": self.pc.localDescription.sdp,
            "type": self.pc.localDescription.type,
        }

    async def handle_ice_candidate(self, candidate_info: Dict[str, Any]) -> None:
        """Add remote ICE candidate received from client via signaling WebSocket."""
        if not self.pc or not AIORTC_AVAILABLE:
            return

        try:
            cand_str = candidate_info.get("candidate", "")
            if not cand_str:
                return

            candidate = candidate_from_sdp(cand_str)
            candidate.sdpMid = candidate_info.get("sdpMid")
            candidate.sdpMLineIndex = candidate_info.get("sdpMLineIndex")
            await self.pc.addIceCandidate(candidate)
        except Exception as exc:
            log.warning("Failed to add ICE candidate for %s: %s", self.source_id, exc)

    async def _consume_video_track(self, track: Any) -> None:
        """Loop reading video frames from WebRTC track and forwarding into CoreMediaRouter."""
        log.info("Starting WebRTC video track ingestion for %s", self.source_id)
        while not self._closed:
            try:
                frame = await track.recv()
                ts_ms = int(time.time() * 1000)

                # Convert av.VideoFrame to BGR ndarray
                img_bgr = frame.to_ndarray(format="bgr24")

                if cv2 is not None:
                    # Encode to JPEG for standard pipeline ingestion
                    ret, jpeg_buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if ret:
                        self.router.ingest_frame(
                            source_id=self.source_id,
                            frame_id=self._frame_seq,
                            source_ts_ms=ts_ms,
                            jpeg_bytes=jpeg_buf.tobytes(),
                        )
                        self._frame_seq += 1
            except asyncio.CancelledError:
                break
            except Exception as exc:
                if not self._closed:
                    log.warning("WebRTC video track error for %s: %s", self.source_id, exc)
                break

    async def _consume_audio_track(self, track: Any) -> None:
        """Loop reading audio frames from WebRTC track and forwarding into CoreMediaRouter."""
        log.info("Starting WebRTC audio track ingestion for %s", self.source_id)
        while not self._closed:
            try:
                frame = await track.recv()
                ts_ms = int(time.time() * 1000)
                # Raw PCM bytes
                pcm_bytes = bytes(frame.planes[0])
                sample_rate = getattr(frame, "sample_rate", 16000)

                self.router.ingest_audio(
                    source_id=self.source_id,
                    source_ts_ms=ts_ms,
                    pcm_bytes=pcm_bytes,
                    sample_rate=sample_rate,
                )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                if not self._closed:
                    log.warning("WebRTC audio track error for %s: %s", self.source_id, exc)
                break

    async def close(self) -> None:
        """Teardown peer connection and consumer tasks."""
        if self._closed:
            return
        self._closed = True

        for task in self._tasks:
            if not task.done():
                task.cancel()

        if self.pc:
            try:
                await self.pc.close()
            except Exception:
                pass
            self.pc = None

        if self.on_close_cb:
            try:
                self.on_close_cb(self.source_id)
            except Exception:
                pass
        log.info("Closed WebRTC peer connection for source %s", self.source_id)
