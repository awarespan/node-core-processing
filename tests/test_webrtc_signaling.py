"""
AWARESPAN — Tests for WebRTC Signaling & Volunteer Portal API
"""

import json
from pathlib import Path
import pytest

from shared.config.settings import get_settings
from node_runtime.media.registry.source_registry import MediaSourceRegistry
from node_runtime.volunteer_gateway.api.portal import VolunteerPortalAPI
from node_runtime.volunteer_gateway.auth.totp import TOTPAuthManager
from node_runtime.volunteer_gateway.sessions.session_manager import VolunteerSessionManager
from node_runtime.volunteer_gateway.transport.webrtc import WebRTCPeerSession, is_webrtc_supported


def test_webrtc_peer_session_creation():
    session = WebRTCPeerSession(source_id="test-vol-01", session_id="sess-01")
    assert session.source_id == "test-vol-01"
    assert session.session_id == "sess-01"
    assert session._closed is False


def test_direct_volunteer_session_creation():
    mgr = VolunteerSessionManager(max_sessions=3, max_cameras=2, max_microphones=2)
    ok, sess, msg = mgr.create_direct_session("192.168.0.50", "both")
    assert ok is True
    assert sess is not None
    assert sess.client_ip == "192.168.0.50"
    assert "camera" in sess.granted_capabilities
    assert "microphone" in sess.granted_capabilities

    # Check quotas
    ok2, sess2, _ = mgr.create_direct_session("192.168.0.51", "both")
    assert ok2 is True

    # Third camera should hit quota limit of 2
    ok3, sess3, err_msg = mgr.create_direct_session("192.168.0.52", "camera")
    assert ok3 is False
    assert "Max concurrent cameras" in err_msg


def test_portal_api_dual_endpoint_config(tmp_path):
    auth_mgr = TOTPAuthManager(secret_file=tmp_path / "totp.json")
    sess_mgr = VolunteerSessionManager()
    reg = MediaSourceRegistry()
    portal_api = VolunteerPortalAPI(auth_mgr, sess_mgr, reg)

    status_code, config = portal_api.handle_config_request()
    assert status_code == 200
    assert config["ok"] is True
    assert "local_endpoints" in config
    assert "remote_endpoint" in config
    assert "transports" in config
    assert "websocket_binary" in config["transports"]
    assert "webrtc_enabled" in config


def test_static_asset_serving_and_traversal_protection(tmp_path):
    static_dir = tmp_path / "static_volunteer"
    static_dir.mkdir(parents=True)
    asset_file = static_dir / "app.js"
    asset_file.write_text("console.log('volunteer-ready');", encoding="utf-8")

    auth_mgr = TOTPAuthManager(secret_file=tmp_path / "totp.json")
    sess_mgr = VolunteerSessionManager()
    portal_api = VolunteerPortalAPI(auth_mgr, sess_mgr, static_dir=str(static_dir))

    # Valid static file fetch
    res = portal_api.render_static_file("app.js")
    assert res is not None
    code, ctype, body = res
    assert code == 200
    assert "javascript" in ctype
    assert b"volunteer-ready" in body

    # Missing file returns None
    assert portal_api.render_static_file("nonexistent.css") is None

    # Path traversal attack attempt returns None
    assert portal_api.render_static_file("../../etc/passwd") is None
