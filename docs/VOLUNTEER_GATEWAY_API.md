# AWARESPAN — Volunteer Media Gateway API & Protocol Specification

**Project:** AWARESPAN  
**Tagline:** Awareness Without Boundaries.  
**Problem Statement:** An AI-Powered Safety Device.  
**Contact:** awarespan@bchbenjamin.in  
**Target:** Raspberry Pi 5 (4 GB RAM), Bookworm / Debian 12  

---

## 1. Overview & Architectural Philosophy

The **Volunteer Media Gateway** provides a LAN-first, zero-cloud ingestion boundary allowing authorized phones, laptops, and browser-equipped devices to temporarily volunteer their cameras and microphones to the AWARESPAN edge node.

### Key Architectural Tenets:
1. **Isolated & Removable Module:** The gateway resides exclusively within `node_runtime/volunteer_gateway/`. It interacts with the rest of the node solely through the reusable media abstraction in `node_runtime/media/routing/media_router.py`. It can be disabled via `--no-volunteer-gateway` or environment configuration (`VOLUNTEER_GATEWAY_ENABLED=false`) without affecting the core inference engine or local camera/microphone inputs.
2. **100% LAN-First / Offline:** Requires no internet connection, no external STUN/TURN servers, no public DNS, and no third-party auth providers (e.g., Firebase, Auth0).
3. **Hardware-Conscious Transport:** Employs a zero-copy binary WebSocket transport protocol that eliminates base64 CPU decoding overhead on the Raspberry Pi 5.
4. **End-to-End Threat Attribution:** All ingested frames and audio packets carry immutable `source_id` provenance, propagating through the YOLOv8 visual detector, threat assessment tiers, deterrent responses, and SQLite event persistence.

---

## 2. Authentication & Authorization (RFC 6238 TOTP)

To prevent unauthorized LAN endpoints from injecting media into the safety device, all volunteers must complete an operator-supervised TOTP challenge.

### 2.1 TOTP Specification
- **Algorithm:** RFC 6238 (HMAC-SHA1, 6-digit output).
- **Time Step:** 30 seconds.
- **Drift Tolerance:** $\pm 1$ step ($\pm 30$ seconds, 3 steps total) to accommodate clock skew across offline LAN devices.
- **Secret Storage:** Pure-Python implementation; persists secret to `state/totp_secret.json` with strict `0600` permissions.
- **Provisioning URI:**
  ```text
  otpauth://totp/AWARESPAN:Pi5?secret=<BASE32_SECRET>&issuer=AWARESPAN&algorithm=SHA1&digits=6&period=30
  ```

### 2.2 Brute-Force Rate Limiting
- **Max Failed Attempts:** 5 consecutive failures per client IP.
- **Lockout Duration:** 300 seconds (5 minutes).
- **Behavior:** Once locked out, requests from that client IP are immediately rejected with HTTP `401 Unauthorized` / `429 Too Many Requests` regardless of code validity.

### 2.3 Single-Use Pairing Tokens
- Upon successful TOTP verification, the server issues a cryptographically random, single-use pairing token (valid for 300 seconds).
- The pairing token encodes the granted capability scope (`camera_only`, `mic_only`, or `both`).
- **Single-Use Enforcement:** The token is immediately marked used upon WebSocket handshake redemption and cannot be reused or hijacked.

---

## 3. REST API Endpoints

The gateway listens by default on `https://0.0.0.0:8443` (configurable via `VOLUNTEER_GATEWAY_PORT`).

### 3.1 Portal Web UI
- **Route:** `GET /` or `GET /index.html`
- **Description:** Serves the compiled or self-contained embedded responsive HTML5/JavaScript volunteer interface.
- **Security Headers:** CSP, HTTPS secure context enablement.

### 3.2 Gateway Discovery & Configuration
- **Route:** `GET /api/volunteer/config`
- **Authentication:** None (LAN discovery).
- **Response `200 OK`:**
  ```json
  {
    "ok": true,
    "success": true,
    "node_id": "node-pi5",
    "name": "AWARESPAN Edge Core",
    "transport": "websocket_binary",
    "max_fps": 15,
    "volunteer_max_fps": 15,
    "ideal_resolution": [640, 480],
    "audio_sample_rate": 16000
  }
  ```

### 3.3 Operator TOTP Verification
- **Route:** `POST /api/volunteer/auth`
- **Request Headers:** `Content-Type: application/json`
- **Request Body:**
  ```json
  {
    "totp_code": "849201",
    "scope": "both",
    "device_name": "Pixel 7 Pro"
  }
  ```
- **Response `200 OK` (Success):**
  ```json
  {
    "ok": true,
    "success": true,
    "message": "Authenticated successfully",
    "pairing_token": "a1b2c3d4e5f6...32bytes",
    "granted_capabilities": ["camera", "microphone"],
    "expires_in": 300,
    "node_id": "node-pi5"
  }
  ```
- **Response `401 Unauthorized` (Invalid Code / Rate Limited):**
  ```json
  {
    "ok": false,
    "success": false,
    "message": "Invalid code. 3 attempts remaining."
  }
  ```

### 3.4 Active Media Sources
- **Route:** `GET /api/volunteer/sources`
- **Description:** Diagnostic endpoint listing active volunteer sessions and media sources.

---

## 4. Binary WebSocket Media Transport Protocol

- **Endpoint:** `wss://<node-ip>:8443/ws/volunteer?token=<PAIRING_TOKEN>`
- **Frame Format:** Big-endian binary frame.

### 4.1 Frame Header Structure (22 bytes minimum + source ID)

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                       Magic: "AWSP"                           |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|   Type (1B)   |  SrcLen (1B)  |   Source ID string (SrcLen B) |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+                               +
|                              ...                              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                       Sequence Number (4B)                    |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                                                               |
+                    Timestamp Milliseconds (8B)                +
|                                                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                       Payload Length (4B)                     |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                       Payload Bytes (PayloadLen B)            |
|                              ...                              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

### 4.2 Packet Types
| Value | Identifier | Payload Format | Description |
|---|---|---|---|
| `0x01` | `FRAME_JPEG` | Raw JPEG bytes | Video camera frame (target: 640x480, quality 65-75). |
| `0x02` | `AUDIO_PCM` | Raw 16-bit PCM | Microphone audio samples (16 kHz, 16-bit mono, LE). |
| `0x03` | `HEARTBEAT` | Empty (`0` bytes) | Periodic keepalive (every 5 seconds). |
| `0x04` | `DISCONNECT`| Empty (`0` bytes) | Graceful volunteer disconnection notice. |

### 4.3 Performance Rationale
1. **Zero Base64 Overhead:** Eliminates 33% bandwidth inflation and CPU decode spikes on the Pi 5.
2. **Direct Memory Mapping:** Ingested JPEG payloads are passed directly to `cv2.imdecode` into memory.
3. **Bounded Backpressure:** If the inference queue is full, the oldest frame is dropped immediately, guaranteeing ultra-low live streaming latency (<80ms on LAN).

---

## 5. TLS & Browser Secure Context Requirements

Mobile and desktop browsers (iOS Safari, Android Chrome, Firefox) strictly enforce **Secure Contexts** (`isSecureContext === true`) before allowing JavaScript to access `navigator.mediaDevices.getUserMedia`.

1. **Automatic Certificate Generation:** On startup, `VolunteerGatewayServer` automatically generates an ephemeral self-signed certificate and key at `state/certs/volunteer_gateway.crt` and `state/certs/volunteer_gateway.key` if not already present.
2. **Acceptance Workflow:** Evaluators/users navigate to `https://<ip>:8443/`, acknowledge the browser's self-signed security prompt once ("Advanced" -> "Proceed to site"), after which camera and microphone access are fully unlocked.
