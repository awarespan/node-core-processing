"""
AWARESPAN — Tests for Remote Connectivity & Tunnel Ingress Manager
"""

import socket
import pytest

from shared.config.settings import get_settings
from node_runtime.volunteer_gateway.tunnel.tunnel_manager import RemoteTunnelManager, get_tunnel_manager


def test_tunnel_manager_initialization():
    mgr = get_tunnel_manager()
    assert mgr is not None
    assert mgr.port > 0
    assert isinstance(mgr.tunnel_type, str)


def test_local_ip_discovery():
    mgr = RemoteTunnelManager()
    ips = mgr.get_local_ips()
    assert isinstance(ips, list)

    for ip in ips:
        # None should be 127.0.0.1 loopback
        assert not ip.startswith("127.")
        # Must be valid IPv4
        socket.inet_aton(ip)


def test_endpoint_resolution_custom_https():
    mgr = RemoteTunnelManager()
    mgr.remote_enabled = True
    mgr.tunnel_type = "custom_https"
    mgr.settings.remote_tunnel_url = "https://safe-node.awarespan.in:8443"

    res = mgr.resolve_remote_endpoint()
    assert res == "https://safe-node.awarespan.in:8443"


def test_endpoint_resolution_disabled():
    mgr = RemoteTunnelManager()
    mgr.remote_enabled = False
    assert mgr.resolve_remote_endpoint() is None

    mgr.remote_enabled = True
    mgr.tunnel_type = "disabled"
    assert mgr.resolve_remote_endpoint() is None


def test_get_active_endpoints_structure():
    mgr = RemoteTunnelManager()
    endpoints = mgr.get_active_endpoints()

    assert "node_id" in endpoints
    assert "mode" in endpoints
    assert "local_endpoints" in endpoints
    assert isinstance(endpoints["local_endpoints"], list)
    assert "remote_endpoint" in endpoints
    assert "tunnel_type" in endpoints
    assert "gateway_port" in endpoints
