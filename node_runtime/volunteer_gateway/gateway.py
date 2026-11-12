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
import http
import json
import os
import ssl
import subprocess
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import websockets

from shared.config.settings import get_settings
from shared.logging.logger import get_logger
from node_runtime.media.registry.source_registry import MediaSourceRegistry, get_source_registry
from node_runtime.media.routing.media_router import CoreMediaRouter, get_media_router
from node_runtime.media.sources.source import MediaSource, SourceOrigin, SourceState, SourceType
from node_runtime.volunteer_gateway.api.portal import VolunteerPortalAPI
from node_runtime.volunteer_gateway.auth.totp import TOTPAuthManager
from node_runtime.volunteer_gateway.sessions.session_manager import VolunteerSession, VolunteerSessionManager
from node_runtime.volunteer_gateway.transport.protocol import (
    DecodedPacket,
    PacketType,
    parse_incoming_message,
)
from node_runtime.volunteer_gateway.transport.webrtc import (
    WebRTCPeerSession,
    is_webrtc_supported,
)
from node_runtime.volunteer_gateway.tunnel.tunnel_manager import get_tunnel_manager

log = get_logger("volunteer_gateway.core")


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
        self._server = None
        self._stop_event = asyncio.Event()

    async def _process_http_request(self, *args, **kwargs):
        """
        Intercept HTTP requests before WebSocket upgrade.
        Supports both websockets legacy (path, headers) and websockets 14+ (connection, request) signatures.
        """
        path = "/"
        client_ip = "127.0.0.1"

        if len(args) == 2 and isinstance(args[0], str):
            path = args[0]
        elif len(args) >= 2:
            conn, req = args[0], args[1]
            path = getattr(req, "path", "/")
            if hasattr(conn, "remote_address") and conn.remote_address:
                client_ip = conn.remote_address[0]

        parsed_url = urllib.parse.urlparse(path)
        route = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        # Allow WebSocket upgrade for /ws/volunteer
        if route == "/ws/volunteer":
            return None

        # 1. GET / -> Serve volunteer portal
        if route in ("/", "/index.html"):
            status_code, content_type, body = self.api.render_portal_html()
            headers = [
                ("Content-Type", content_type),
                ("Content-Length", str(len(body.encode("utf-8")))),
                ("Access-Control-Allow-Origin", "*"),
                ("Connection", "close"),
            ]
            return (http.HTTPStatus(status_code), headers, body.encode("utf-8"))

        # 2. Check for static asset files in configured static dir
        if not route.startswith("/api/"):
            static_res = self.api.render_static_file(route)
            if static_res:
                status_code, content_type, body_bytes = static_res
                headers = [
                    ("Content-Type", content_type),
                    ("Content-Length", str(len(body_bytes))),
                    ("Access-Control-Allow-Origin", "*"),
                    ("Connection", "close"),
                ]
                return (http.HTTPStatus(status_code), headers, body_bytes)

        # 3. GET /api/volunteer/config
        if route == "/api/volunteer/config":
            status_code, data = self.api.handle_config_request()
            payload = json.dumps(data).encode("utf-8")
            headers = [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(payload))),
                ("Access-Control-Allow-Origin", "*"),
                ("Connection", "close"),
            ]
            return (http.HTTPStatus(status_code), headers, payload)

        # 4. GET /api/volunteer/sources
        elif route == "/api/volunteer/sources":
            status_code, data = self.api.handle_status_request()
            payload = json.dumps(data).encode("utf-8")
            headers = [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(payload))),
                ("Access-Control-Allow-Origin", "*"),
                ("Connection", "close"),
            ]
            return (http.HTTPStatus(status_code), headers, payload)

        # 5. /api/volunteer/auth
        elif route == "/api/volunteer/auth":
            totp_code = query.get("totp_code", [""])[0]
            capability = query.get("capability", ["both"])[0]
            if totp_code:
                status_code, data = self.api.handle_auth_request(
                    {"totp_code": totp_code, "capability": capability},
                    client_ip,
                )
                payload = json.dumps(data).encode("utf-8")
                headers = [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(payload))),
                    ("Access-Control-Allow-Origin", "*"),
                    ("Connection", "close"),
                ]
                return (http.HTTPStatus(status_code), headers, payload)
            else:
                headers = [
                    ("Access-Control-Allow-Origin", "*"),
                    ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
                    ("Access-Control-Allow-Headers", "Content-Type, Authorization"),
                    ("Connection", "close"),
                ]
                return (http.HTTPStatus.OK, headers, b'{"ok": true}')

        # 6. Handle CORS preflight
        elif route.startswith("/api/"):
            headers = [
                ("Access-Control-Allow-Origin", "*"),
                ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
                ("Access-Control-Allow-Headers", "Content-Type, Authorization"),
                ("Connection", "close"),
            ]
            return (http.HTTPStatus.OK, headers, b"")

        # 404 Not Found
        return (http.HTTPStatus.NOT_FOUND, [("Connection", "close")], b"Not Found")

    async def _handle_websocket(self, websocket):
        """Handle active volunteer device WebSocket connection with signaling and binary transport."""
        parsed_url = urllib.parse.urlparse(getattr(websocket, "path", "/"))
        query_params = urllib.parse.parse_qs(parsed_url.query)
        client_ip = websocket.remote_address[0] if websocket.remote_address else "127.0.0.1"

        log.info("Incoming volunteer WebSocket from %s", client_ip)
        token = query_params.get("token", [""])[0]
        session: Optional[VolunteerSession] = None
        webrtc_session: Optional[WebRTCPeerSession] = None

        # Check if paired via URL query token
        if token:
            ok, sess, msg = self.session_mgr.redeem_pairing_token(token, client_ip)
            if ok and sess:
                session = sess
                self._register_session_source(session, client_ip)
                await websocket.send(json.dumps({
                    "type": "authorized",
                    "source_id": session.source_id,
                    "session_id": session.session_id,
                    "message": "Connected to AWARESPAN Edge Core",
                }))
            else:
                log.warning("Pairing token redemption rejected: %s", msg)
                await websocket.send(json.dumps({"type": "error", "message": msg}))
                await websocket.close(1008, msg)
                return

        try:
            async for message in websocket:
                # Text Frame: Control plane, auth, and WebRTC signaling
                if isinstance(message, str):
                    try:
                        data = json.loads(message)
                    except Exception:
                        continue

                    mtype = data.get("type", "")

                    # 1. Direct WebSocket Authentication
                    if mtype == "auth" and not session:
                        totp_code = str(data.get("totp_code", "")).strip()
                        cap_str = str(data.get("capability", "both")).lower()
                        caps = {"camera", "microphone"}
                        if cap_str in ("camera", "camera_only"):
                            caps = {"camera"}
                        elif cap_str in ("microphone", "mic_only"):
                            caps = {"microphone"}

                        success, msg = self.auth_mgr.verify_attempt(client_ip, totp_code)
                        if not success:
                            await websocket.send(json.dumps({"type": "error", "message": msg}))
                            await websocket.close(1008, msg)
                            return

                        ok, sess, msg = self.session_mgr.create_direct_session(client_ip, caps)
                        if not ok or not sess:
                            await websocket.send(json.dumps({"type": "error", "message": msg}))
                            await websocket.close(1008, msg)
                            return

                        session = sess
                        self._register_session_source(session, client_ip)
                        await websocket.send(json.dumps({
                            "type": "authorized",
                            "source_id": session.source_id,
                            "session_id": session.session_id,
                            "granted_capabilities": list(caps),
                            "message": "Authorized by operator TOTP",
                        }))
                        continue

                    if not session:
                        # Unauthorized message
                        await websocket.send(json.dumps({"type": "error", "message": "Unauthorized"}))
                        continue

                    self.session_mgr.record_activity(session.session_id)
                    self.registry.record_heartbeat(session.source_id)

                    # 2. WebRTC SDP Offer
                    if mtype == "webrtc_offer":
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
                                await websocket.send(json.dumps({
                                    "type": "webrtc_answer",
                                    "sdp": answer["sdp"],
                                    "sdp_type": answer["type"],
                                }))
                            except Exception as exc:
                                log.warning("WebRTC offer negotiation error for %s: %s", session.source_id, exc)
                                await websocket.send(json.dumps({"type": "fallback", "message": str(exc)}))
                        else:
                            log.info("WebRTC not supported on server; requesting binary WS fallback")
                            await websocket.send(json.dumps({"type": "fallback", "message": "WebRTC unavailable"}))

                    # 3. WebRTC ICE Candidate
                    elif mtype == "ice_candidate":
                        if webrtc_session:
                            await webrtc_session.handle_ice_candidate(data)

                    # 4. Keepalive Ping
                    elif mtype == "ping":
                        await websocket.send(json.dumps({"type": "pong", "timestamp": int(time.time() * 1000)}))

                    # 5. Disconnect signal
                    elif mtype == "disconnect":
                        log.info("Volunteer %s sent disconnect signal", session.source_id)
                        break

                # Binary Frame: Direct AWSP Media Stream
                elif isinstance(message, bytes):
                    if not session:
                        continue

                    self.session_mgr.record_activity(session.session_id)
                    self.registry.record_heartbeat(session.source_id)

                    pkt = parse_incoming_message(message, fallback_source_id=session.source_id)
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

        except websockets.exceptions.ConnectionClosed:
            log.debug("Volunteer connection closed for %s", getattr(session, "source_id", "unauth"))
        except Exception as exc:
            log.warning("Exception in volunteer connection handler: %s", exc)
        finally:
            if webrtc_session:
                await webrtc_session.close()

            if session:
                log.info("Volunteer source %s disconnected", session.source_id)
                self.registry.update_state(session.source_id, SourceState.DISCONNECTED, reason="Transport closed")
                self.session_mgr.revoke_session(session.session_id, reason="Connection ended")

    def _register_session_source(self, session: VolunteerSession, client_ip: str) -> None:
        """Register active volunteer device into central MediaSourceRegistry."""
        caps = session.granted_capabilities
        stype = SourceType.COMBINED if len(caps) > 1 else (SourceType.CAMERA if "camera" in caps else SourceType.MICROPHONE)

        media_src = MediaSource(
            source_id=session.source_id,
            node_id=get_settings().node_id,
            source_type=stype,
            source_origin=SourceOrigin.BROWSER_VOLUNTEER,
            display_name=f"Volunteer Device ({client_ip})",
            session_id=session.session_id,
            connection_state=SourceState.CONNECTING,
            transport="webrtc_ws",
            capabilities={"granted": list(caps)},
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
        ssl_ctx = self._get_ssl_context() if self.use_tls else None
        proto = "https/wss" if ssl_ctx else "http/ws"

        self._server = await websockets.serve(
            self._handle_websocket,
            self.host,
            self.port,
            process_request=self._process_http_request,
            ssl=ssl_ctx,
            max_size=2**24,
            ping_interval=15,
            ping_timeout=20,
        )
        log.info("AWARESPAN Volunteer Media Gateway active on %s://%s:%d", proto, self.host, self.port)

    async def stop(self) -> None:
        """Stop the volunteer gateway server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            log.info("Volunteer Media Gateway stopped.")


async def run_standalone_gateway():
    """Standalone entrypoint for running the volunteer gateway as an independent process."""
    settings = get_settings()
    gateway = VolunteerGatewayServer(
        host=settings.volunteer_gateway_host,
        port=settings.volunteer_gateway_port,
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
