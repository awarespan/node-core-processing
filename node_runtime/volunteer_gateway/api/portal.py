"""
AWARESPAN — Volunteer Web Portal & REST API
Exposes pairing API, dual-endpoint discovery, static asset serving, and responsive HTML5 portal UI.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import json
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from shared.config.settings import get_settings
from shared.logging.logger import get_logger
from node_runtime.media.registry.source_registry import MediaSourceRegistry, get_source_registry
from node_runtime.volunteer_gateway.auth.totp import TOTPAuthManager
from node_runtime.volunteer_gateway.sessions.session_manager import VolunteerSessionManager
from node_runtime.volunteer_gateway.transport.webrtc import is_webrtc_supported
from node_runtime.volunteer_gateway.tunnel.tunnel_manager import get_tunnel_manager

log = get_logger("volunteer_gateway.api")


# Embedded, self-contained offline responsive HTML5 volunteer portal with WebRTC + binary WS fallback
OFFLINE_PORTAL_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AWARESPAN Volunteer Gateway</title>
<style>
:root { --bg: #0d1117; --card: #161b22; --accent: #238636; --accent-hover: #2ea043; --danger: #da3633; --text: #c9d1d9; --text-muted: #8b949e; --border: #30363d; --blue: #58a6ff; }
body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 16px; display: flex; flex-direction: column; align-items: center; min-height: 100vh; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; width: 100%; max-width: 480px; padding: 20px; box-sizing: border-box; margin-bottom: 16px; }
h1 { font-size: 1.3rem; margin: 0 0 4px 0; color: #fff; display: flex; justify-content: space-between; align-items: center; }
.node-pill { font-size: 0.7rem; font-weight: normal; background: #21262d; padding: 3px 8px; border-radius: 10px; border: 1px solid var(--border); color: var(--blue); }
.tagline { color: var(--text-muted); font-size: 0.85rem; margin-bottom: 16px; }
.net-info { font-size: 0.75rem; background: #010409; padding: 8px 12px; border-radius: 6px; border: 1px solid var(--border); margin-bottom: 16px; color: var(--text-muted); }
.field { margin-bottom: 12px; }
label { display: block; font-size: 0.85rem; color: var(--text-muted); margin-bottom: 4px; }
input, select { width: 100%; padding: 10px; background: #010409; border: 1px solid var(--border); border-radius: 6px; color: #fff; box-sizing: border-box; font-size: 1rem; }
button { width: 100%; padding: 12px; background: var(--accent); color: #fff; border: none; border-radius: 6px; font-size: 1rem; font-weight: 600; cursor: pointer; transition: background 0.2s; }
button:hover { background: var(--accent-hover); }
button.danger { background: var(--danger); margin-top: 8px; }
.status-badge { display: inline-block; padding: 4px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: bold; }
.status-active { background: rgba(35, 134, 54, 0.2); color: #3fb950; border: 1px solid #3fb950; }
.status-idle { background: rgba(139, 148, 158, 0.2); color: #8b949e; border: 1px solid #8b949e; }
video { width: 100%; border-radius: 6px; background: #000; margin-top: 10px; transform: scaleX(-1); }
#videoPreview { display: none; }
.stats { font-size: 0.8rem; color: var(--text-muted); margin-top: 8px; line-height: 1.4; }
</style>
</head>
<body>
<div class="card">
  <h1>AWARESPAN <span class="node-pill" id="nodePill">Edge Core</span></h1>
  <div class="tagline">Awareness Without Boundaries &bull; Volunteer Portal</div>
  <div class="net-info" id="netInfo">Detecting network environment...</div>

  <div id="authSection">
    <div class="field">
      <label for="totpCode">Operator 6-Digit TOTP Code</label>
      <input type="text" id="totpCode" pattern="[0-9]*" inputmode="numeric" placeholder="123456" maxlength="6" autofocus>
    </div>
    <div class="field">
      <label for="capability">Device Role</label>
      <select id="capability">
        <option value="both">Camera & Microphone</option>
        <option value="camera">Camera Only</option>
        <option value="microphone">Microphone Only</option>
      </select>
    </div>
    <button id="btnAuth">Authorize & Connect</button>
  </div>

  <div id="liveSection" style="display:none;">
    <div>Status: <span id="connStatus" class="status-badge status-idle">Connecting</span></div>
    <video id="videoPreview" autoplay playsinline muted></video>
    <div class="stats" id="streamStats">Connecting to edge inference pipeline...</div>
    <button class="danger" id="btnStop">Disconnect Stream</button>
  </div>
  <div id="msgBox" style="margin-top:12px;font-size:0.85rem;color:#f85149;"></div>
</div>

<script>
let ws = null, stream = null, canvas = null, timer = null, frameCount = 0, seqId = 0, pc = null;
let nodeConfig = { webrtc_enabled: true, stun_servers: [] };
const $ = id => document.getElementById(id);

async function loadConfig() {
  try {
    const res = await fetch('/api/volunteer/config');
    nodeConfig = await res.json();
    if (nodeConfig.node_id) $('nodePill').innerText = nodeConfig.node_id;
    const isRemote = location.hostname.includes('.ts.net') || location.hostname !== '127.0.0.1' && !location.hostname.startsWith('192.168.');
    $('netInfo').innerHTML = `Mode: <b>${isRemote ? 'Remote Ingress' : 'Local LAN / Hotspot'}</b> &bull; Transports: ${nodeConfig.transports ? nodeConfig.transports.join(', ') : 'WebRTC, WS'}`;
  } catch(e) {
    $('netInfo').innerText = "Mode: Direct LAN Connection";
  }
}
loadConfig();

$('btnAuth').onclick = async () => {
  const code = $('totpCode').value.trim();
  const cap = $('capability').value;
  if (!code || code.length !== 6) {
    $('msgBox').innerText = "Please enter the 6-digit TOTP code.";
    return;
  }
  $('msgBox').innerText = "";
  $('msgBox').style.color = "#c9d1d9";
  $('msgBox').innerText = "Verifying with AWARESPAN Core...";

  const wantVideo = cap === 'both' || cap === 'camera';
  const wantAudio = cap === 'both' || cap === 'microphone';

  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: wantVideo ? { width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 10 } } : false,
      audio: wantAudio
    });
    if (wantVideo) {
      $('videoPreview').style.display = 'block';
      $('videoPreview').srcObject = stream;
      canvas = document.createElement('canvas');
      canvas.width = 640; canvas.height = 480;
    }
  } catch(e) {
    $('msgBox').style.color = "#f85149";
    $('msgBox').innerText = "Media permission denied: " + e.message;
    return;
  }

  // Connect WebSocket control plane
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/ws/volunteer`);
  ws.binaryType = 'arraybuffer';

  ws.onopen = () => {
    // Send direct auth frame
    ws.send(JSON.stringify({ type: 'auth', totp_code: code, capability: cap }));
  };

  ws.onmessage = async (evt) => {
    if (typeof evt.data === 'string') {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === 'authorized') {
          $('authSection').style.display = 'none';
          $('liveSection').style.display = 'block';
          $('connStatus').className = "status-badge status-active";
          $('connStatus').innerText = "AUTHORIZED";

          if (nodeConfig.webrtc_enabled && window.RTCPeerConnection) {
            startWebRTC(cap);
          } else {
            startBinaryWsStreaming(wantVideo);
          }
        } else if (msg.type === 'webrtc_answer' && pc) {
          await pc.setRemoteDescription(new RTCSessionDescription({ type: msg.sdp_type || 'answer', sdp: msg.sdp }));
        } else if (msg.type === 'fallback') {
          startBinaryWsStreaming(wantVideo);
        } else if (msg.type === 'error') {
          $('msgBox').style.color = "#f85149";
          $('msgBox').innerText = "Authentication error: " + (msg.message || "Failed");
          stopAll();
        }
      } catch(err) {
        console.error("Signal parsing error:", err);
      }
    }
  };

  ws.onclose = () => {
    $('connStatus').className = "status-badge status-idle";
    $('connStatus').innerText = "DISCONNECTED";
    stopAll();
  };
};

async function startWebRTC(cap) {
  try {
    $('connStatus').innerText = "NEGOTIATING WEBRTC";
    const iceServers = (nodeConfig.stun_servers || []).map(s => ({ urls: s }));
    pc = new RTCPeerConnection({ iceServers });

    stream.getTracks().forEach(t => pc.addTrack(t, stream));

    pc.onicecandidate = (e) => {
      if (e.candidate && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: 'ice_candidate',
          candidate: e.candidate.candidate,
          sdpMid: e.candidate.sdpMid,
          sdpMLineIndex: e.candidate.sdpMLineIndex
        }));
      }
    };

    pc.onconnectionstatechange = () => {
      if (pc.connectionState === 'connected') {
        $('connStatus').className = "status-badge status-active";
        $('connStatus').innerText = "LIVE (WebRTC RTP)";
        $('streamStats').innerText = "Transport: WebRTC (Sub-second Edge Streaming)";
      } else if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected') {
        startBinaryWsStreaming(cap === 'both' || cap === 'camera');
      }
    };

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    ws.send(JSON.stringify({ type: 'webrtc_offer', sdp: offer.sdp, sdp_type: offer.type }));
  } catch(e) {
    console.warn("WebRTC startup failed; falling back to binary WS:", e);
    startBinaryWsStreaming(cap === 'both' || cap === 'camera');
  }
}

function startBinaryWsStreaming(wantVideo) {
  if (timer) clearInterval(timer);
  $('connStatus').className = "status-badge status-active";
  $('connStatus').innerText = "LIVE (Binary WebSocket)";
  if (wantVideo) {
    timer = setInterval(sendFrame, 100); // 10 FPS
  }
}

function sendFrame() {
  if (!ws || ws.readyState !== WebSocket.OPEN || !canvas) return;
  const ctx = canvas.getContext('2d');
  ctx.drawImage($('videoPreview'), 0, 0, canvas.width, canvas.height);
  canvas.toBlob(blob => {
    if (!blob) return;
    blob.arrayBuffer().then(buf => {
      const bytes = new Uint8Array(buf);
      const srcId = "browser-cam";
      const pLen = bytes.length;
      const pkt = new Uint8Array(22 + srcId.length + pLen);
      // Magic: AWSP
      pkt[0] = 0x41; pkt[1] = 0x57; pkt[2] = 0x53; pkt[3] = 0x50;
      pkt[4] = 0x01; // Frame
      pkt[5] = srcId.length;
      for (let i=0; i<srcId.length; i++) pkt[6+i] = srcId.charCodeAt(i);
      let off = 6 + srcId.length;
      const view = new DataView(pkt.buffer);
      view.setUint32(off, seqId++);
      view.setBigUint64(off+4, BigInt(Date.now()));
      view.setUint32(off+12, pLen);
      pkt.set(bytes, off+16);
      ws.send(pkt.buffer);
      frameCount++;
      $('streamStats').innerText = `Frames sent: ${frameCount} | Transport: Binary WebSocket (AWSP)`;
    });
  }, 'image/jpeg', 0.65);
}

function stopAll() {
  if (timer) clearInterval(timer);
  if (stream) stream.getTracks().forEach(t => t.stop());
  if (pc) { try { pc.close(); } catch(e){} pc = null; }
  if (ws && ws.readyState === WebSocket.OPEN) ws.close();
}

$('btnStop').onclick = () => { stopAll(); location.reload(); };
</script>
</body>
</html>
"""


class VolunteerPortalAPI:
    """Handles REST request dispatch, dual-endpoint configuration, and portal UI rendering."""

    def __init__(
        self,
        auth_mgr: TOTPAuthManager,
        session_mgr: VolunteerSessionManager,
        registry: Optional[MediaSourceRegistry] = None,
        static_dir: Optional[str] = None,
    ):
        self.auth_mgr = auth_mgr
        self.session_mgr = session_mgr
        self.registry = registry or get_source_registry()
        self.settings = get_settings()
        self.static_dir = Path(static_dir) if static_dir else Path(self.settings.volunteer_portal_static_dir)

    def handle_auth_request(self, post_data: Union[bytes, Dict[str, Any]], client_ip: str) -> Tuple[int, Dict[str, Any]]:
        """
        Verify TOTP code and issue single-use pairing token.
        POST /api/volunteer/auth
        """
        if isinstance(post_data, dict):
            data = post_data
        else:
            try:
                data = json.loads(post_data.decode("utf-8"))
            except Exception:
                return 400, {"ok": False, "success": False, "message": "Invalid JSON body"}

        code = str(data.get("totp_code", "")).strip()
        capability_str = str(data.get("capability", data.get("scope", "both"))).lower()

        caps = {"camera", "microphone"}
        if capability_str in ("camera", "camera_only"):
            caps = {"camera"}
        elif capability_str in ("microphone", "mic_only"):
            caps = {"microphone"}

        success, msg = self.auth_mgr.verify_attempt(client_ip, code)
        if not success:
            return 401, {"ok": False, "success": False, "message": msg}

        ok, token, token_msg = self.session_mgr.issue_pairing_token(caps)
        if not ok:
            return 429, {"ok": False, "success": False, "message": token_msg}

        return 200, {
            "ok": True,
            "success": True,
            "message": "Authenticated successfully",
            "pairing_token": token,
            "granted_capabilities": list(caps),
            "expires_in": int(self.session_mgr.pairing_timeout),
            "node_id": self.settings.node_id,
        }

    def handle_status_request(self) -> Tuple[int, Dict[str, Any]]:
        """
        Return active sessions and sources overview.
        GET /api/volunteer/sources
        """
        sources = [s.to_dict() for s in self.registry.list_sources()]
        sessions = [s.to_dict() for s in self.session_mgr.list_active_sessions()]
        return 200, {
            "ok": True,
            "node_id": self.settings.node_id,
            "active_sources": sources,
            "active_sessions": sessions,
        }

    def handle_config_request(self) -> Tuple[int, Dict[str, Any]]:
        """
        Return dual endpoint discovery document and streaming parameters for frontend client.
        GET /api/volunteer/config
        """
        tunnel_mgr = get_tunnel_manager()
        endpoints_info = tunnel_mgr.get_active_endpoints()

        return 200, {
            "ok": True,
            "success": True,
            "node_id": self.settings.node_id,
            "name": "AWARESPAN Edge Core",
            "tagline": "Awareness Without Boundaries.",
            "mode": endpoints_info.get("mode", "local_only"),
            "local_endpoints": endpoints_info.get("local_endpoints", []),
            "remote_endpoint": endpoints_info.get("remote_endpoint"),
            "tunnel_type": endpoints_info.get("tunnel_type"),
            "transports": ["webrtc", "websocket_binary"] if is_webrtc_supported() else ["websocket_binary"],
            "webrtc_enabled": is_webrtc_supported() and getattr(self.settings, "webrtc_enabled", True),
            "stun_servers": getattr(self.settings, "stun_servers", []),
            "turn_configured": bool(getattr(self.settings, "turn_url", "")),
            "max_fps": 15,
            "volunteer_max_fps": 15,
            "ideal_resolution": [640, 480],
            "audio_sample_rate": 16000,
        }

    def render_static_file(self, relative_path: str) -> Optional[Tuple[int, str, bytes]]:
        """
        Serve static asset (.js, .css, .svg, .png, etc.) from static_dir.
        Returns (status_code, content_type, bytes) or None if not found or unsafe path.
        """
        if not self.static_dir.exists():
            return None

        # Sanitize against path traversal attacks
        rel = relative_path.lstrip("/\\")
        try:
            target_file = (self.static_dir / rel).resolve()
            target_file.relative_to(self.static_dir.resolve())
        except (ValueError, RuntimeError):
            return None

        if not target_file.is_file():
            return None

        ctype, _ = mimetypes.guess_type(str(target_file))
        ctype = ctype or "application/octet-stream"
        try:
            return 200, ctype, target_file.read_bytes()
        except Exception as exc:
            log.warning("Could not read static asset %s: %s", target_file, exc)
            return None

    def render_portal_html(self) -> Tuple[int, str, str]:
        """
        Serve compiled static index.html or embedded fallback UI.
        Returns (status_code, content_type, body).
        """
        index_file = self.static_dir / "index.html"
        if index_file.is_file():
            try:
                return 200, "text/html; charset=utf-8", index_file.read_text(encoding="utf-8")
            except Exception as exc:
                log.warning("Could not read static index.html: %s; using embedded UI", exc)

        return 200, "text/html; charset=utf-8", OFFLINE_PORTAL_HTML
