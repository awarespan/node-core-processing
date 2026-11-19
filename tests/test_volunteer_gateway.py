"""
AWARESPAN — Volunteer Gateway Unit Tests
Tests TOTP RFC 6238 authentication, rate limiting, session lifecycle, and binary transport framing.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import asyncio
import asyncio
import json
import time
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest
import websockets

from node_runtime.volunteer_gateway.auth.totp import TOTPAuthManager
from node_runtime.volunteer_gateway.sessions.session_manager import (
    PairingScope,
    VolunteerSessionManager,
)
from node_runtime.volunteer_gateway.transport.protocol import (
    MAGIC_HEADER,
    PacketType,
    encode_binary_packet,
    parse_incoming_message,
)
from node_runtime.volunteer_gateway.api.portal import VolunteerPortalAPI
from node_runtime.volunteer_gateway.gateway import VolunteerGatewayServer
from node_runtime.media.registry.source_registry import MediaSourceRegistry
from node_runtime.media.routing.media_router import CoreMediaRouter
from node_runtime.volunteer_gateway.gateway import VolunteerGatewayServer


def test_totp_auth_and_verification(tmp_path):
    secret_file = tmp_path / "totp_secret.txt"
    auth_mgr = TOTPAuthManager(secret_file=secret_file)

    code, rem = auth_mgr.get_current_token()
    assert len(code) == 6
    assert code.isdigit()
    assert 0 <= rem <= 30

    # Verify code succeeds
    assert auth_mgr.verify_token(code, client_ip="192.168.4.10") is True

    # Wrong code fails
    wrong_code = "000000" if code != "000000" else "999999"
    assert auth_mgr.verify_token(wrong_code, client_ip="192.168.4.10") is False


def test_totp_rate_limiting(tmp_path):
    secret_file = tmp_path / "totp_secret.txt"
    auth_mgr = TOTPAuthManager(secret_file=secret_file, max_failed_attempts=3, lockout_window_sec=60)

    client_ip = "192.168.4.99"
    # 3 failed attempts
    for _ in range(3):
        assert auth_mgr.verify_token("000000", client_ip=client_ip) is False

    # 4th attempt should be blocked by rate limit
    is_limited, rem_time = auth_mgr.is_rate_limited(client_ip)
    assert is_limited is True
    assert rem_time > 0

    # Even valid code must be rejected when locked out
    valid_code, _ = auth_mgr.get_current_token()
    assert auth_mgr.verify_token(valid_code, client_ip=client_ip) is False


def test_session_manager_pairing_and_single_use():
    session_mgr = VolunteerSessionManager(pairing_timeout_sec=30)

    pairing_token = session_mgr.create_pairing_token(
        client_ip="192.168.4.15",
        scope=PairingScope.CAMERA_ONLY,
    )
    assert len(pairing_token) >= 16

    # Redeem pairing token
    ok, session, msg = session_mgr.redeem_pairing_token(
        token=pairing_token,
        client_ip="192.168.4.15",
        device_name="Evaluator iPhone",
    )
    assert ok is True
    assert session is not None
    assert session.device_name == "Evaluator iPhone"
    assert session.can_camera is True
    assert session.can_microphone is False

    # Second redemption attempt MUST fail (single-use token)
    ok2, second_attempt, msg2 = session_mgr.redeem_pairing_token(
        token=pairing_token,
        client_ip="192.168.4.15",
    )
    assert ok2 is False
    assert second_attempt is None


def test_session_manager_quotas():
    # Only allow 1 camera
    session_mgr = VolunteerSessionManager(max_cameras=1, max_microphones=1, max_sessions=2)

    tok1 = session_mgr.create_pairing_token("1.1.1.1", scope=PairingScope.CAMERA_ONLY)
    tok2 = session_mgr.create_pairing_token("1.1.1.2", scope=PairingScope.CAMERA_ONLY)

    ok1, s1, _ = session_mgr.redeem_pairing_token(tok1, "1.1.1.1")
    assert ok1 is True
    assert s1 is not None

    # Exceeding camera quota should reject redemption
    ok2, s2, _ = session_mgr.redeem_pairing_token(tok2, "1.1.1.2")
    assert ok2 is False
    assert s2 is None


def test_binary_protocol_encode_decode():
    source_id = "vol-test-src"
    payload = b"\xde\xad\xbe\xef" * 16
    seq = 42
    ts = 1700000000123

    raw_bytes = encode_binary_packet(
        packet_type=PacketType.FRAME,
        source_id=source_id,
        sequence=seq,
        timestamp_ms=ts,
        payload=payload,
    )

    assert raw_bytes.startswith(MAGIC_HEADER)

    decoded = parse_incoming_message(raw_bytes)
    assert decoded.packet_type == PacketType.FRAME
    assert decoded.source_id == source_id
    assert decoded.sequence == seq
    assert decoded.timestamp_ms == ts
    assert decoded.payload == payload


def test_portal_api(tmp_path):
    secret_file = tmp_path / "totp_secret.txt"
    auth_mgr = TOTPAuthManager(secret_file=secret_file)
    session_mgr = VolunteerSessionManager()
    registry = MediaSourceRegistry()

    api = VolunteerPortalAPI(auth_mgr, session_mgr, registry)

    # 1. Config request
    status, config = api.handle_config_request()
    assert status == 200
    assert "node_id" in config
    assert "volunteer_max_fps" in config

    # 2. Auth request with valid TOTP code
    valid_code, _ = auth_mgr.get_current_token()
    status, resp = api.handle_auth_request(
        post_data={"totp_code": valid_code, "scope": "both", "device_name": "Test Phone"},
        client_ip="192.168.4.20",
    )
    assert status == 200
    assert resp["success"] is True
    assert "pairing_token" in resp

    # 3. Auth request with invalid code
    status, resp = api.handle_auth_request(
        post_data={"totp_code": "000000" if valid_code != "000000" else "111111"},
        client_ip="192.168.4.20",
    )
    assert status == 401
    assert resp["success"] is False


def test_gateway_auth_uses_post_headers_and_never_query_string(tmp_path):
    async def _run():
        secret_file = tmp_path / "totp_secret.json"
        auth_mgr = TOTPAuthManager(secret_file=secret_file)
        session_mgr = VolunteerSessionManager(pairing_timeout_sec=300, session_timeout_sec=3600)
        registry = MediaSourceRegistry()
        gateway = object.__new__(VolunteerGatewayServer)
        gateway.api = VolunteerPortalAPI(auth_mgr, session_mgr, registry)

        code, _ = auth_mgr.get_current_token()
        connection = SimpleNamespace(remote_address=("198.51.100.20", 54000))
        request = SimpleNamespace(
            path="/api/volunteer/auth",
            method="POST",
            headers={
                "X-TOTP-Code": code,
                "X-Volunteer-Capability": "camera",
                "X-Operator-ID": "operator-test",
                "Origin": "https://portal.example.test",
            },
        )
        status, headers, body = await gateway._process_http_request_routes(connection, request)
        response = json.loads(body)

        assert int(status) == 200
        assert response["success"] is True
        assert response["granted_capabilities"] == ["camera"]
        assert response["pairing_expires_in"] == 300
        assert response["session_expires_in"] == 3600
        assert response["pairing_token"]
        assert any(k.lower() == "access-control-allow-origin" and v == "*" for k, v in headers)
    asyncio.run(_run())

def test_gateway_auth_preflight_and_get_query_are_safe(tmp_path):
    async def _run():
        auth_mgr = TOTPAuthManager(secret_file=tmp_path / "totp_secret.json")
        gateway = object.__new__(VolunteerGatewayServer)
        gateway.api = VolunteerPortalAPI(auth_mgr, VolunteerSessionManager(), MediaSourceRegistry())
        connection = SimpleNamespace(remote_address=("198.51.100.21", 54000))

        preflight = SimpleNamespace(path="/api/volunteer/auth", method="OPTIONS", headers={})
        status, headers, body = await gateway._process_http_request_routes(connection, preflight)
        assert int(status) == 200
        assert body == b""
        allow_headers = next(v for k, v in headers if k.lower() == "access-control-allow-headers")
        assert "X-TOTP-Code" in allow_headers

        legacy_get = SimpleNamespace(
            path="/api/volunteer/auth?totp_code=123456",
            method="GET",
            headers={},
        )
        status, headers, body = await gateway._process_http_request_routes(connection, legacy_get)
        assert int(status) == 405
        assert b"query-string authentication is disabled" in body
    asyncio.run(_run())

def test_live_gateway_http_pairing_websocket_and_binary_frame_pipeline(tmp_path):
    async def _run():
        """Exercise the listening HTTP + WebSocket server, not a mocked route helper."""
        from node_runtime.volunteer_gateway.transport.protocol import pack_binary_packet

        secret_file = tmp_path / "totp_secret.json"
        auth_mgr = TOTPAuthManager(secret_file=secret_file)
        registry = MediaSourceRegistry()
        router = CoreMediaRouter(registry=registry)
        session_mgr = VolunteerSessionManager(
            max_sessions=2, max_cameras=2, max_microphones=1,
            pairing_timeout_sec=30, session_timeout_sec=120,
        )
        gateway = object.__new__(VolunteerGatewayServer)
        gateway.host = "127.0.0.1"
        gateway.port = 0
        gateway.registry = registry
        gateway.router = router
        gateway.use_tls = False
        gateway.auth_mgr = auth_mgr
        gateway.session_mgr = session_mgr
        gateway.api = VolunteerPortalAPI(auth_mgr, session_mgr, registry)
        gateway._server = None
        gateway._stop_event = asyncio.Event()

        await gateway.start()
        try:
            port = gateway._server.sockets[0].getsockname()[1]
            base_url = f"http://127.0.0.1:{port}"

            def request_get(path, headers=None, method="GET"):
                request = urllib.request.Request(base_url + path, method=method, headers=headers or {})
                with urllib.request.urlopen(request, timeout=5) as response:
                    return response.status, response.headers, response.read()

            root_status, root_headers, _ = await asyncio.to_thread(request_get, "/")
            assert root_status == 200
            assert "text/html" in root_headers.get("Content-Type", "")
            config_status, _, config_body = await asyncio.to_thread(request_get, "/api/volunteer/config")
            assert config_status == 200
            assert json.loads(config_body.decode("utf-8"))["ok"] is True
            options_status, options_headers, _ = await asyncio.to_thread(
                request_get, "/api/volunteer/auth",
                {"Origin": "https://portal.example.test", "Access-Control-Request-Method": "POST"},
                "OPTIONS",
            )
            assert options_status == 200
            assert options_headers.get("Access-Control-Allow-Origin") == "*"

            code, _ = auth_mgr.get_current_token()
            auth_url = f"{base_url}/api/volunteer/auth"

            def request_pairing_token():
                request = urllib.request.Request(
                    auth_url, data=b"", method="POST",
                    headers={
                        "X-TOTP-Code": code,
                        "X-Operator-ID": "operator-test",
                        "X-Volunteer-Capability": "camera",
                        "Origin": "https://portal.example.test",
                    },
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    return response.status, response.headers, json.loads(response.read())

            status, headers, auth_data = await asyncio.to_thread(request_pairing_token)
            assert status == 200
            assert auth_data["success"] is True
            assert auth_data["granted_capabilities"] == ["camera"]
            assert auth_data["pairing_token"]
            assert headers.get("Access-Control-Allow-Origin") == "*"

            ws_url = f"ws://127.0.0.1:{port}/ws/volunteer"
            async with websockets.connect(ws_url) as websocket:
                await websocket.send(json.dumps({"type": "pairing_token", "token": auth_data["pairing_token"]}))
                authorised = json.loads(await asyncio.wait_for(websocket.recv(), timeout=5))
                assert authorised["type"] == "authorized"
                assert authorised["granted_capabilities"] == ["camera"]
                source_id = authorised["source_id"]

                jpeg_payload = b"\xff\xd8\xffAWARESPAN_TEST_FRAME\xff\xd9"
                packet = pack_binary_packet(
                    PacketType.FRAME_JPEG, source_id="portal", seq_id=7,
                    timestamp_ms=int(time.time() * 1000), payload=jpeg_payload,
                )
                await websocket.send(packet)
                for _ in range(30):
                    source = registry.get_source(source_id)
                    if source and source.metrics["frames_received"] >= 1:
                        break
                    await asyncio.sleep(0.02)
                assert source is not None
                assert source.camera_active is True
                assert source.metrics["frames_received"] == 1
                assert source.metrics["last_frame_id"] == 7

            # Pairing tokens are single-use; a second redemption must be rejected.
            async with websockets.connect(ws_url) as second_socket:
                await second_socket.send(json.dumps({"type": "pairing_token", "token": auth_data["pairing_token"]}))
                rejected = json.loads(await asyncio.wait_for(second_socket.recv(), timeout=5))
                assert rejected["type"] == "error"
                assert "already been redeemed" in rejected["message"]
        finally:
            await gateway.stop()
    asyncio.run(_run())