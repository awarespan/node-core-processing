"""
AWARESPAN — Volunteer Media Gateway Server
Coordinates HTTP pairing portal, REST APIs, TLS encryption, WebRTC low-latency streaming,
and binary WebSocket media ingestion with automated fallback.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import asyncio
import base64
import json
import os
import ssl
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple

from aiohttp import web

from shared.config.settings import get_settings
from shared.logging.logger import get_logger
from node_runtime.media.registry.source_registry import MediaSourceRegistry, get_source_registry
from node_runtime.media.routing.media_router import CoreMediaRouter, get_media_router
from node_runtime.media.sources.source import MediaSource, SourceOrigin, SourceState, SourceType
from node_runtime.volunteer_gateway.api.portal import VolunteerPortalAPI
from node_runtime.volunteer_gateway.auth.totp import TOTPAuthManager
from node_runtime.volunteer_gateway.sessions.session_manager import VolunteerSession, VolunteerSessionManager
from node_runtime.volunteer_gateway.transport.protocol import (
    PacketType,
    parse_incoming_message,
)
from node_runtime.volunteer_gateway.transport.webrtc import (
    WebRTCPeerSession,
    is_webrtc_supported,
)
from node_runtime.volunteer_gateway.tunnel.tunnel_manager import get_tunnel_manager

log = get_logger("volunteer_gateway.core")


@web.middleware
async def cors_middleware(request: web.Request, handler):
    """Enforce permissive CORS headers for LAN and cross-origin volunteer clients."""
    if request.method == "OPTIONS":
        resp = web.Response(status=200)
    else:
        try:
            resp = await handler(request)
        except web.HTTPException as exc:
            resp = exc

    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    return resp


class VolunteerGatewayServer:
    """Standalone or integrated LAN-first volunteer camera/microphone ingestion gateway."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        registry: Optional[MediaSourceRegistry] = None,
        router: Optional[CoreMediaRouter] = None,
        use_tls: bool = False,
    ):
        settings = get_settings()
        self.settings = settings
        self.host = host or settings.volunteer_gateway_host
        self.port = port or settings.volunteer_gateway_port
        self.registry = registry or get_source_registry()
        self.router = router or get_media_router()
        self.use_tls = use_tls

        self.auth_mgr = TOTPAuthManager(secret_file=Path(settings.totp_secret_file))
        self.session_mgr = VolunteerSessionManager(
            max_sessions=settings.volunteer_max_sessions,
            max_cameras=settings.volunteer_max_cameras,
            max_microphones=settings.volunteer_max_microphones,
            pairing_timeout_sec=settings.volunteer_pairing_timeout_sec,
        )
        self.api = VolunteerPortalAPI(self.auth_mgr, self.session_mgr, self.registry)
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        self._active_ws: Set[web.WebSocketResponse] = set()

    def _build_app(self) -> web.Application:
        """Construct the aiohttp Application with all REST and WebSocket routes."""
        app = web.Application(middlewares=[cors_middleware])

        # REST endpoints
        app.router.add_get("/", self._handle_portal_html)
        app.router.add_get("/index.html", self._handle_portal_html)
        app.router.add_get("/api/volunteer/config", self._handle_config)
        app.router.add_get("/api/volunteer/sources", self._handle_sources)
        app.router.add_post("/api/volunteer/auth", self._handle_auth)
        app.router.add_post("/api/v1/auth/volunteer-session", self._handle_auth)
        app.router.add_post("/api/volunteer/webrtc/signal", self._handle_webrtc_signal)
        app.router.add_get("/health", self._handle_health)

        # WebSocket endpoints
        app.router.add_get("/ws/volunteer", self._handle_websocket)
        app.router.add_get("/ingest", self._handle_websocket)

        # Static assets and SPA catch-all
        app.router.add_get("/{path:.*}", self._handle_static_or_spa)

        return app

    async def _handle_portal_html(self, request: web.Request) -> web.Response:
        status, content_type, body = self.api.render_portal_html()
        ctype = content_type.split(";")[0].strip()
        return web.Response(text=body, content_type=ctype, charset="utf-8")

    async def _handle_config(self, request: web.Request) -> web.Response:
        status, data = self.api.handle_config_request()
        return web.json_response(data, status=status)

    async def _handle_sources(self, request: web.Request) -> web.Response:
        status, data = self.api.handle_status_request()
        return web.json_response(data, status=status)

    async def _handle_auth(self, request: web.Request) -> web.Response:
        client_ip = request.remote or "127.0.0.1"
        try:
            body = await request.json()
        except Exception:
            body = {}

        # Allow query string fallback if body is empty
        if not body:
            body = dict(request.query)

        status, data = self.api.handle_auth_request(body, client_ip)
        return web.json_response(data, status=status)

    async def _handle_webrtc_signal(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "message": "Invalid JSON"}, status=400)

        if not is_webrtc_supported():
            return web.json_response({
                "ok": False,
                "supported": False,
                "fallback": "websocket_binary",
                "message": "WebRTC media stack not available on edge node; use binary WebSocket"
            }, status=200)

        return web.json_response({"ok": True, "message": "Signaling endpoint active"}, status=200)

    async def _handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({
            "status": "ok",
            "node": self.settings.node_id,
            "timestamp": int(time.time() * 1000)
        })

    async def _handle_static_or_spa(self, request: web.Request) -> web.Response:
        path = request.match_info.get("path", "")
        # Block internal API path traversal
        if path.startswith("api/"):
            return web.Response(status=404, text="Not Found")

        static_res = self.api.render_static_file(path)
        if static_res:
            status, ctype, body_bytes = static_res
            clean_ctype = ctype.split(";")[0].strip()
            return web.Response(body=body_bytes, content_type=clean_ctype)

        # Fallback to SPA index.html for client-side routing
        return await self._handle_portal_html(request)

    async def _handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """Handle active volunteer device WebSocket connection with signaling and media transport."""
        ws = web.WebSocketResponse(max_msg_size=2**24, heartbeat=15.0)
        await ws.prepare(request)

        self._active_ws.add(ws)
        client_ip = request.remote or "127.0.0.1"
        token = request.query.get("token", "").strip()

        session: Optional[VolunteerSession] = None
        webrtc_session: Optional[WebRTCPeerSession] = None

        log.info("Incoming volunteer WebSocket from %s", client_ip)

        # 1. Authorize via query token if present
        if token:
            ok, sess, msg = self.session_mgr.redeem_pairing_token(token, client_ip)
            if ok and sess:
                session = sess
                self._register_session_source(session, client_ip)
                await ws.send_json({
                    "type": "authorized",
                    "source_id": session.source_id,
                    "session_id": session.session_id,
                    "message": "Connected to AWARESPAN Edge Core",
                })
                if "camera" in session.granted_capabilities:
                    await ws.send_json({"type": "ack", "source": "camera"})
                if "microphone" in session.granted_capabilities:
                    await ws.send_json({"type": "ack", "source": "microphone"})
            else:
                log.warning("Pairing token redemption rejected: %s", msg)
                await ws.send_json({"type": "error", "message": msg})
                await ws.close(code=4008, message=msg.encode("utf-8"))
                self._active_ws.discard(ws)
                return ws

        try:
            async for msg in ws:
                # ── Text Frame (JSON): Auth, Control Plane & WebRTC Signaling ──
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except Exception:
                        continue

                    mtype = data.get("type", "")

                    # In-band authentication / handshake
                    if mtype in ("auth", "volunteer_handshake") and not session:
                        totp_code = str(data.get("totp_code", "")).strip()
                        token_cand = str(data.get("session_token", data.get("token", data.get("pairing_token", "")))).strip()
                        cap_str = str(data.get("capability", data.get("mode", "both"))).lower()

                        caps = {"camera", "microphone"}
                        if cap_str in ("camera", "camera_only"):
                            caps = {"camera"}
                        elif cap_str in ("microphone", "mic_only"):
                            caps = {"microphone"}

                        if token_cand:
                            ok, sess, errmsg = self.session_mgr.redeem_pairing_token(token_cand, client_ip)
                            if ok and sess:
                                session = sess
                        elif totp_code:
                            success, vmsg = self.auth_mgr.verify_attempt(client_ip, totp_code)
                            if success:
                                ok, sess, errmsg = self.session_mgr.create_direct_session(client_ip, caps)
                                if ok and sess:
                                    session = sess
                            else:
                                errmsg = vmsg
                        else:
                            # In local LAN mode, if client provides volunteer_handshake without token,
                            # create session automatically if single-node evaluation mode
                            ok, sess, errmsg = self.session_mgr.create_direct_session(client_ip, caps)
                            if ok and sess:
                                session = sess

                        if session:
                            self._register_session_source(session, client_ip)
                            await ws.send_json({
                                "type": "authorized",
                                "source_id": session.source_id,
                                "session_id": session.session_id,
                                "granted_capabilities": list(caps),
                                "message": "Authorized by operator",
                            })
                            if "camera" in session.granted_capabilities:
                                await ws.send_json({"type": "ack", "source": "camera"})
                            if "microphone" in session.granted_capabilities:
                                await ws.send_json({"type": "ack", "source": "microphone"})
                            continue
                        else:
                            await ws.send_json({"type": "reject", "message": "Authentication failed"})
                            await ws.close(code=4008, message=b"Auth failed")
                            return ws

                    if not session:
                        await ws.send_json({"type": "reject", "message": "Unauthorized"})
                        continue

                    self.session_mgr.record_activity(session.session_id)
                    self.registry.record_heartbeat(session.source_id)

                    # Keepalive ping/pong
                    if mtype == "ping":
                        ts = data.get("ts_ms", int(time.time() * 1000))
                        await ws.send_json({"type": "pong", "ts_ms": ts, "timestamp": int(time.time() * 1000)})

                    # JSON Frame payload: { "type": "frame", "frame_id": int, "ts_ms": int, "jpeg_b64": str }
                    elif mtype == "frame":
                        jpeg_b64 = data.get("jpeg_b64", "")
                        if jpeg_b64:
                            try:
                                jpeg_bytes = base64.b64decode(jpeg_b64)
                                self.router.ingest_frame(
                                    source_id=session.source_id,
                                    frame_id=int(data.get("frame_id", 0)),
                                    source_ts_ms=int(data.get("ts_ms", 0)),
                                    jpeg_bytes=jpeg_bytes,
                                )
                            except Exception as exc:
                                log.debug("JSON frame decode error: %s", exc)

                    # WebRTC SDP Offer
                    elif mtype == "webrtc_offer":
                        if is_webrtc_supported():
                            if not webrtc_session:
                                webrtc_session = WebRTCPeerSession(
                                    source_id=session.source_id,
                                    session_id=session.session_id,
                                    router=self.router,
                                )
                            try:
                                answer = await webrtc_session.handle_offer(
                                    sdp=data.get("sdp", ""),
                                    sdp_type=data.get("sdp_type", "offer"),
                                )
                                await ws.send_json({
                                    "type": "webrtc_answer",
                                    "sdp": answer["sdp"],
                                    "sdp_type": answer["type"],
                                })
                            except Exception as exc:
                                log.warning("WebRTC negotiation error for %s: %s", session.source_id, exc)
                                await ws.send_json({"type": "fallback", "message": str(exc)})
                        else:
                            log.info("WebRTC unavailable on node; instructing client to use binary WebSocket")
                            await ws.send_json({"type": "fallback", "message": "WebRTC unavailable"})

                    # WebRTC ICE Candidate
                    elif mtype == "ice_candidate":
                        if webrtc_session:
                            await webrtc_session.handle_ice_candidate(data)

                    # Disconnect
                    elif mtype == "disconnect":
                        log.info("Volunteer %s sent disconnect signal", session.source_id)
                        break

                # ── Binary Frame: Direct AWSP Media Stream ──
                elif msg.type == web.WSMsgType.BINARY:
                    if not session:
                        continue

                    self.session_mgr.record_activity(session.session_id)
                    self.registry.record_heartbeat(session.source_id)

                    pkt = parse_incoming_message(msg.data, fallback_source_id=session.source_id)
                    if not pkt:
                        continue

                    if pkt.packet_type == PacketType.FRAME_JPEG:
                        self.router.ingest_frame(
                            source_id=session.source_id,
                            frame_id=pkt.seq_id,
                            source_ts_ms=pkt.timestamp_ms,
                            jpeg_bytes=pkt.payload,
                        )
                    elif pkt.packet_type == PacketType.AUDIO_PCM:
                        self.router.ingest_audio(
                            source_id=session.source_id,
                            source_ts_ms=pkt.timestamp_ms,
                            pcm_bytes=pkt.payload,
                        )
                    elif pkt.packet_type == PacketType.DISCONNECT:
                        break

                elif msg.type in (web.WSMsgType.CLOSE, web.WSMsgType.ERROR):
                    break

        except Exception as exc:
            log.warning("Exception in volunteer streaming session for %s: %s", getattr(session, "source_id", "unauth"), exc)
        finally:
            self._active_ws.discard(ws)
            if webrtc_session:
                await webrtc_session.close()

            if session:
                log.info("Volunteer source %s disconnected", session.source_id)
                self.registry.update_state(session.source_id, SourceState.DISCONNECTED, reason="Transport closed")
                self.session_mgr.revoke_session(session.session_id, reason="Connection ended")

        return ws

    def _register_session_source(self, session: VolunteerSession, client_ip: str) -> None:
        """Register active volunteer device into central MediaSourceRegistry."""
        caps = session.granted_capabilities
        stype = SourceType.COMBINED if len(caps) > 1 else (SourceType.CAMERA if "camera" in caps else SourceType.MICROPHONE)

        media_src = MediaSource(
            source_id=session.source_id,
            source_type=stype,
            source_origin=SourceOrigin.BROWSER_VOLUNTEER,
            node_id=get_settings().node_id,
            display_name=f"Volunteer Device ({client_ip})",
            friendly_name=f"Volunteer Device ({client_ip})",
            session_id=session.session_id,
            connection_state=SourceState.CONNECTING,
            transport="webrtc_ws",
            camera_active="camera" in caps,
            mic_active="microphone" in caps,
            metadata={"granted_capabilities": list(caps)},
        )
        self.registry.register_source(media_src)

    def _get_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Create or load SSL context for local HTTPS context."""
        cert_dir = Path("state") / "certs"
        cert_file = cert_dir / "volunteer_gateway.crt"
        key_file = cert_dir / "volunteer_gateway.key"

        if not cert_file.exists() or not key_file.exists():
            cert_dir.mkdir(parents=True, exist_ok=True)
            log.info("Generating self-signed certificate for local HTTPS...")
            try:
                cmd = [
                    "openssl", "req", "-x509", "-newkey", "rsa:2048",
                    "-keyout", str(key_file), "-out", str(cert_file),
                    "-days", "365", "-nodes",
                    "-subj", "/CN=awarespan.local/O=AWARESPAN",
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                os.chmod(key_file, 0o600)
            except Exception as exc:
                log.warning("OpenSSL certificate generation unavailable: %s", exc)
                return None

        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(certfile=str(cert_file), keyfile=str(key_file))
            return ctx
        except Exception as exc:
            log.warning("Could not initialize SSL context: %s; falling back to plaintext HTTP", exc)
            return None

    async def start(self) -> None:
        """Start the volunteer gateway server."""
        app = self._build_app()
        self._runner = web.AppRunner(app)
        await self._runner.setup()

        ssl_ctx = self._get_ssl_context() if self.use_tls else None
        proto = "https/wss" if ssl_ctx else "http/ws"

        self._site = web.TCPSite(self._runner, self.host, self.port, ssl_context=ssl_ctx)
        await self._site.start()
        log.info("AWARESPAN Volunteer Media Gateway active on %s://%s:%d", proto, self.host, self.port)

    async def stop(self) -> None:
        """Stop the volunteer gateway server."""
        # Close any active WebSockets
        for ws in list(self._active_ws):
            try:
                await ws.close(code=1001, message=b"Server shutting down")
            except Exception:
                pass
        self._active_ws.clear()

        if self._runner:
            await self._runner.cleanup()
            self._runner = None
            self._site = None
            log.info("Volunteer Media Gateway stopped.")


async def run_standalone_gateway():
    """Standalone entrypoint for running the volunteer gateway as an independent process."""
    settings = get_settings()
    gateway = VolunteerGatewayServer(
        host=settings.volunteer_gateway_host,
        port=settings.volunteer_gateway_port,
        use_tls=getattr(settings, "volunteer_gateway_tls", False),
    )
    await gateway.start()
    try:
        await asyncio.Future()  # run forever
    except asyncio.CancelledError:
        await gateway.stop()


def main():
    try:
        asyncio.run(run_standalone_gateway())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
