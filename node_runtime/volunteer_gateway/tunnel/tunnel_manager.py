"""
AWARESPAN — Remote Tunnel & Ingress Discovery Manager
Detects local network interfaces (Wi-Fi, AP hotspot, Ethernet) and manages remote
ingress tunnels (Tailscale, Cloudflare Tunnel, Custom HTTPS) for volunteer media streaming.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import json
import os
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.config.settings import get_settings
from shared.logging.logger import get_logger

log = get_logger("volunteer_gateway.tunnel")


class RemoteTunnelManager:
    """
    Manages local endpoint discovery and remote ingress tunneling
    supporting Tailscale (Funnel & MagicDNS), Cloudflare Tunnel, and custom HTTPS reverse proxies.
    """

    def __init__(self):
        self.settings = get_settings()
        self.port = getattr(self.settings, "volunteer_gateway_port", 8443)
        self.use_tls = getattr(self.settings, "volunteer_gateway_tls", True)
        self.scheme = "https" if self.use_tls else "http"
        self.tunnel_type = getattr(self.settings, "tunnel_type", "tailscale").lower()
        self.remote_enabled = getattr(self.settings, "remote_connectivity_enabled", True)

    def get_local_ips(self) -> List[str]:
        """Discover active local IPv4 addresses on all interfaces (excluding loopback)."""
        ips: List[str] = []
        try:
            import psutil
            for iface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        ip = addr.address
                        # Exclude loopback and Tailscale CGNAT from pure local LAN list
                        if not ip.startswith("127.") and not ip.startswith("100."):
                            if ip not in ips:
                                ips.append(ip)
        except Exception:
            # Fallback using standard socket probe
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
                if ip and not ip.startswith("127.") and ip not in ips:
                    ips.append(ip)
            except Exception:
                pass

        # Ensure configured AP Gateway IP is included if not present (e.g. offline field hotspot)
        ap_ip = getattr(self.settings, "ap_gateway_ip", "192.168.4.1")
        if ap_ip and ap_ip not in ips and not ap_ip.startswith("127."):
            # Include AP IP so clients pairing over hotspot can reach it
            ips.append(ap_ip)

        return ips

    def get_tailscale_info(self) -> Dict[str, Any]:
        """Query Tailscale daemon for MagicDNS hostname, IPv4, and funnel status."""
        tailscale_bin = shutil.which("tailscale")
        if not tailscale_bin:
            return {"available": False}

        try:
            res = subprocess.run(
                [tailscale_bin, "status", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=4,
                check=False,
            )
            if res.returncode == 0 and res.stdout:
                data = json.loads(res.stdout)
                self_node = data.get("Self", {})
                dns_name = self_node.get("DNSName", "").rstrip(".")
                tailscale_ips = self_node.get("TailscaleIPs", [])
                ipv4 = next((ip for ip in tailscale_ips if "." in ip), "")

                return {
                    "available": True,
                    "dns_name": dns_name,
                    "tailscale_ip": ipv4,
                    "host_name": self_node.get("HostName", ""),
                    "online": self_node.get("Online", False),
                }
        except Exception as exc:
            log.debug("Tailscale status query: %s", exc)

        return {"available": False}

    def resolve_remote_endpoint(self) -> Optional[str]:
        """
        Determine the stable remote HTTPS ingress endpoint for volunteers outside the LAN.
        Follows priority:
        1. Explicit settings.remote_tunnel_url
        2. Tailscale MagicDNS / Funnel endpoint
        3. Cloudflare Tunnel URL
        """
        if not self.remote_enabled or self.tunnel_type == "disabled":
            return None

        # 1. Explicitly configured remote URL
        explicit_url = getattr(self.settings, "remote_tunnel_url", "").strip()
        if explicit_url:
            return explicit_url.rstrip("/")

        # 2. Tailscale provider
        if self.tunnel_type == "tailscale":
            ts_info = self.get_tailscale_info()
            if ts_info.get("available"):
                dns_name = ts_info.get("dns_name")
                if dns_name:
                    # Check if port is 443 (standard funnel) or custom port
                    port_str = f":{self.port}" if self.port not in (80, 443) else ""
                    return f"https://{dns_name}{port_str}"
                elif ts_info.get("tailscale_ip"):
                    port_str = f":{self.port}" if self.port not in (80, 443) else ""
                    return f"http://{ts_info['tailscale_ip']}{port_str}"

        # 3. Cloudflared provider
        if self.tunnel_type == "cloudflared":
            # Check state/cloudflared.url if exists
            state_file = Path("state/cloudflared.url")
            if state_file.is_file():
                try:
                    url = state_file.read_text(encoding="utf-8").strip()
                    if url.startswith("http"):
                        return url.rstrip("/")
                except Exception:
                    pass

        return None

    def get_active_endpoints(self) -> Dict[str, Any]:
        """
        Assemble comprehensive endpoint discovery document for frontend clients and QR codes.
        Returns both local LAN endpoints and remote ingress endpoint.
        """
        local_ips = self.get_local_ips()
        local_endpoints = [f"{self.scheme}://{ip}:{self.port}" for ip in local_ips]

        remote_endpoint = self.resolve_remote_endpoint()
        ts_info = self.get_tailscale_info()

        return {
            "node_id": self.settings.node_id,
            "mode": "dual" if remote_endpoint else "local_only",
            "local_endpoints": local_endpoints,
            "remote_endpoint": remote_endpoint,
            "tunnel_type": self.tunnel_type,
            "remote_enabled": self.remote_enabled,
            "tailscale_ip": ts_info.get("tailscale_ip") if ts_info.get("available") else None,
            "tailscale_dns": ts_info.get("dns_name") if ts_info.get("available") else None,
            "gateway_port": self.port,
            "gateway_tls": self.use_tls,
        }


# Global singleton instance
_tunnel_manager: Optional[RemoteTunnelManager] = None


def get_tunnel_manager() -> RemoteTunnelManager:
    global _tunnel_manager
    if _tunnel_manager is None:
        _tunnel_manager = RemoteTunnelManager()
    return _tunnel_manager
