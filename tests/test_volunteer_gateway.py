"""
AWARESPAN — Volunteer Gateway Unit Tests
Tests TOTP RFC 6238 authentication, rate limiting, session lifecycle, and binary transport framing.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import time
import pytest
from pathlib import Path

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
from node_runtime.media.registry.source_registry import MediaSourceRegistry


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
