"""
AWARESPAN — Volunteer Web Portal & REST API
Exposes local pairing API, serves compiled or embedded offline volunteer UI, and enforces secure headers.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from shared.config.settings import get_settings
from shared.logging.logger import get_logger
from node_runtime.media.registry.source_registry import MediaSourceRegistry, get_source_registry
from node_runtime.volunteer_gateway.auth.totp import TOTPAuthManager
from node_runtime.volunteer_gateway.sessions.session_manager import VolunteerSessionManager

log = get_logger("volunteer_gateway.api")


# Embedded, self-contained offline responsive HTML5 volunteer portal
OFFLINE_PORTAL_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AWARESPAN Volunteer Portal</title>
<style>
:root { --bg: #0d1117; --card: #161b22; --accent: #238636; --accent-hover: #2ea043; --danger: #da3633; --text: #c9d1d9; --text-muted: #8b949e; --border: #30363d; }
body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 16px; display: flex; flex-direction: column; align-items: center; min-height: 100vh; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; width: 100%; max-width: 480px; padding: 20px; box-sizing: border-box; margin-bottom: 16px; }
h1 { font-size: 1.3rem; margin: 0 0 4px 0; color: #fff; }
.tagline { color: var(--text-muted); font-size: 0.85rem; margin-bottom: 16px; }
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
  <h1>AWARESPAN</h1>
  <div class="tagline">Awareness Without Boundaries &bull; Volunteer Portal</div>
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
    <div class="stats" id="streamStats">Frames sent: 0 | Latency: -- ms</div>
    <button class="danger" id="btnStop">Disconnect Stream</button>
  </div>
  <div id="msgBox" style="margin-top:12px;font-size:0.85rem;"></div>
</div>
<script>
let ws = null, stream = null, canvas = null, timer = null, frameCount = 0, seqId = 0;
const $ = id => document.getElementById(id);
$('btnAuth').onclick = async () => {
  const code = $('totpCode').value.trim();
  const cap = $('capability').value;
  $('msgBox').innerText = "Verifying TOTP...";
  try {
    const res = await fetch('/api/volunteer/auth', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({totp_code: code, capability: cap})
    });
    const data = await res.json();
    if (!data.ok) { $('msgBox').innerText = "Error: " + data.message; return; }
    $('msgBox').innerText = "";
    $('authSection').style.display = 'none';
    $('liveSection').style.display = 'block';
    startStreaming(data.pairing_token, cap);
  } catch(e) { $('msgBox').innerText = "Connection failed: " + e.message; }
};
async function startStreaming(token, cap) {
  const wantVideo = cap === 'both' || cap === 'camera';
  const wantAudio = cap === 'both' || cap === 'microphone';
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: wantVideo ? {width: {ideal: 640}, height: {ideal: 480}, frameRate: {ideal: 10}} : false,
      audio: wantAudio
    });
    if (wantVideo) {
      $('videoPreview').style.display = 'block';
      $('videoPreview').srcObject = stream;
      canvas = document.createElement('canvas');
      canvas.width = 640; canvas.height = 480;
    }
  } catch(e) { $('msgBox').innerText = "Media permission denied: " + e.message; return; }
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/ws/volunteer?token=${token}`);
  ws.binaryType = 'arraybuffer';
  ws.onopen = () => {
    $('connStatus').className = "status-badge status-active";
    $('connStatus').innerText = "LIVE STREAMING";
    if (wantVideo) timer = setInterval(sendFrame, 100); // 10 FPS
  };
  ws.onclose = () => {
    $('connStatus').className = "status-badge status-idle";
    $('connStatus').innerText = "DISCONNECTED";
    stopAll();
  };
}
function sendFrame() {
  if (!ws || ws.readyState !== WebSocket.OPEN || !canvas) return;
  const ctx = canvas.getContext('2d');
  ctx.drawImage($('videoPreview'), 0, 0, canvas.width, canvas.height);
  canvas.toBlob(blob => {
    if (!blob) return;
    blob.arrayBuffer().then(buf => {
      // Send binary frame
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
      $('streamStats').innerText = `Frames sent: ${frameCount} | Transport: Binary WebSocket`;
    });
  }, 'image/jpeg', 0.65);
}
function stopAll() {
  if (timer) clearInterval(timer);
  if (stream) stream.getTracks().forEach(t => t.stop());
  if (ws && ws.readyState === WebSocket.OPEN) ws.close();
}
$('btnStop').onclick = () => { stopAll(); location.reload(); };
</script>
</body>
</html>
"""


class VolunteerPortalAPI:
    """Handles REST request dispatch and portal HTML rendering."""

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
        Return local gateway configuration for frontend client discovery.
        GET /api/volunteer/config
        """
        return 200, {
            "ok": True,
            "success": True,
            "node_id": self.settings.node_id,
            "name": "AWARESPAN Edge Core",
            "transport": "websocket_binary",
            "max_fps": 15,
            "volunteer_max_fps": 15,
            "ideal_resolution": [640, 480],
            "audio_sample_rate": 16000,
        }

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
