# AWARESPAN — Raspberry Pi Edge Node Integration & Contract Specification

**Module:** Volunteer Media Ingestion Interface
**Authoritative Backend:** `node-core-processing` (`node-backend`)
**Specification Version:** `1.0.0-temp`
**Target Environment:** Raspberry Pi 5 (Edge Inference Node)

---

## 1. Executive Summary & Existing Node Analysis

Before constructing this frontend, the existing `node-core-processing` (`node-backend`) repository was thoroughly inspected to identify existing listeners, client scripts, network ports, protocols, and authentication mechanics.

### 1.1 Verified Findings in `node-core-processing`

| Characteristic | Live Repository Implementation | File Source |
| :--- | :--- | :--- |
| **Network Port** | `8766` (Configurable via `RUNTIME_PORT` environment variable) | `shared/config/settings.py` (`runtime_port: int = 8766`) |
| **Bind Host** | `0.0.0.0` (Configurable via `RUNTIME_HOST`) | `shared/config/settings.py` (`runtime_host: str = "0.0.0.0"`) |
| **Active Listener** | `websockets.serve(core.route_connection, host, port)` | `node_runtime/main.py:256` |
| **Health Probe** | Path `ws://<host>:8766/health` &rarr; responds with node ID and audio capability fields, then closes | `node_runtime/main.py` |
| **Frame Ingest Path** | Path `ws://<host>:8766/ingest` &rarr; reads JSON frame messages | `node_runtime/main.py:74-75, 79-94` |
| **Dashboard Path** | Path `ws://<host>:8766/` &rarr; broadcasts annotated frames and threat events | `node_runtime/main.py:76-77, 95-110` |
| **Existing Client** | Python OpenCV client capturing webcams and streaming Base64 JPEGs | `laptop/stream_client.py` |
| **Inference Engine** | Ultralytics YOLOv8n (`yolov8n_best_weapon.pt`) + Threat Assessor | `node_runtime/detection/visual/detector.py` |
| **Audio Classifier** | Passive stub (`classify_wav`) without active network streaming socket | `node_runtime/detection/audio/audio_classifier.py` |

---

## 2. Ingestion Protocol Specification (Visual Frames)

The portal adheres strictly to the existing schema parsed by `node_runtime/main.py:processor_loop`:

### Frame Payload (Client &rarr; Pi over `ws://<host>:8766/ingest`)

```json
{
  "type": "frame",
  "frame_id": 1420,
  "ts_ms": 1794424649000,
  "jpeg_b64": "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP..."
}
```

### Protocol Properties:
- **Encoding:** JPEG formatted image converted to ASCII Base64.
- **Recommended Framerate:** 10–12 FPS (to balance inference throughput with Pi thermal envelope).
- **Recommended Resolution:** 640&times;360 or 640&times;480 (matches YOLOv8 640 imgsz default).

---

## 3. Documented Missing Backend Functionality

Visual frame streaming is operational. Operator authentication remains a separate security requirement. Volunteer microphone input is deliberately disabled until its ingestion path is implemented and advertised by the Pi:

### 3.1 Operator Authentication & Token Handshake
* **Current Limitation:** The existing `/ingest` WebSocket opens without checking credentials or tokens.
* **Required Interface:** An authentication endpoint allowing the operator to verify their 6-digit TOTP code and receive a short-lived single-use volunteer token:
  ```http
  POST /api/v1/auth/volunteer-session HTTP/1.1
  Host: 192.168.1.50:8766
  Content-Type: application/json

  {
    "operator_id": "operator-alpha",
    "totp_code": "582194",
    "client_type": "volunteer_portal"
  }
  ```
  **Response (200 OK):**
  ```json
  {
    "status": "authorized",
    "session_token": "vol-session-4f8a9e2b10",
    "expires_at": 1794425549000
  }
  ```

### 3.2 Source Acknowledgement (ACK)
* **Implemented:** The Pi sends an explicit `ack` for camera mode only. The portal changes source state only after receiving the Pi's ACK; opening a WebSocket is not treated as an ACK.
* **Microphone:** No microphone ACK is sent. The current node does not ingest volunteer microphone audio.

### 3.3 Audio Stream Ingestion Interface — Disabled
* **Current Limitation:** `node_runtime/detection/audio/audio_classifier.py` is in passive file mode. No live WebSocket route exists for audio.
* **Safety behaviour:** The portal does not request microphone permissions in production unless a future Pi capability explicitly advertises a working microphone input path. The current Pi reports this capability as unavailable and rejects `audio_chunk` messages. The temporary website is therefore camera-only in production; mock mode remains available for UI tests.

### 3.4 Raspberry Pi &rarr; Telegram Connect/Disconnect Notifications
* **Constraint:** Per architectural requirements, the frontend **never** sends Telegram messages directly and contains no bot tokens. All notifications originate strictly on the Pi.
* **Node Implementation Patch:**
  Add to `node_runtime/main.py`:
  ```python
  from node_runtime.monitoring.telegram_notify import send_message

  async def _ingest_handler(self, websocket):
      node_id = self.settings.node_id
      log.info("Frame ingestion client connected")
      send_message(f"📡 <b>AWARESPAN Source Connected</b>\nNode: <code>{node_id}</code>\nSource: <b>Volunteer Device</b>")
      try:
          async for message in websocket:
              data = json.loads(message)
              if data.get("type") == "frame":
                  self._enqueue_frame(data)
      except Exception as exc:
          log.debug("Ingestion connection ended: %s", exc)
      finally:
          log.info("Frame ingestion client disconnected")
          send_message(f"⚠️ <b>AWARESPAN Source Disconnected</b>\nNode: <code>{node_id}</code>\nSource: <b>Volunteer Device</b>")
  ```

---

## 4. Temporary Utility Retirement Path

When dedicated hardware sensors (RPi Camera Module 3 NoIR & ReSpeaker 2-Mic HAT) are physically deployed:
1. The volunteer portal process is retired without modifying `node_runtime/main.py`.
2. Hardware drivers in `node_runtime/detection/sensors/hardware.py` will feed `frame_queue` directly from the CSI bus and I2S bus.
3. No cloud API or intermediary server decommissioning is required, as none was introduced.

## 5. Annotated Detection Evidence (Pi &rarr; Portal)

The Pi already draws detection boxes during inference and publishes the resulting JPEG on its read-only dashboard WebSocket (`ws://<pi_host>:8766/`). The temporary portal now subscribes to that dashboard feed while its volunteer ingest session is active.

### Detection event

```json
{
  "type": "log",
  "event": {
    "event_id": "evt-...",
    "ts_ms": 1794424649000,
    "tier": "tier1",
    "labels": ["person"],
    "max_confidence": 0.91,
    "action": "alert",
    "frame_id": 1420,
    "source_id": "ws-ingest"
  }
}
```

### Matching Pi-annotated frame

```json
{
  "type": "frame",
  "frame_id": 1420,
  "ts_ms": 1794424649000,
  "source_id": "ws-ingest",
  "annotated_b64": "<base64-encoded-jpeg-with-detection-boxes>",
  "latency_ms": 54,
  "fps": 9
}
```

The portal matches the event and annotated image by `source_id` plus `frame_id`. It displays the JPEG that the Pi generated; it does not infer or draw substitute bounding boxes in the browser. The most recent eight evidence items are retained in the current page session. A frame that does not arrive within the matching window is shown as an event without an image, not as fabricated evidence.

## 6. Pi-Owned Deterrence Output

The temporary portal has no sound generator, audio preview, or playback control. The Raspberry Pi is the sole owner of deterrence output. It creates a short, bounded audible warning signal locally and starts playback through its configured ALSA output only after the runtime detects a playback interface and the speaker feature is enabled. A fresh pitch is sampled for each successful generation within the configured 900–1100 Hz audible-warning band. This is an attention signal, not a validated dog repellent or a claim that any sound will prevent habituation. The actual acoustic sound-pressure level must be measured on the installed speaker/amplifier; digital amplitude alone does not establish safe SPL.

The Pi also sends the same annotated detection JPEG to Telegram through `sendPhoto`, with event ID, labels and confidence in the caption. Telegram photo delivery is asynchronous and does not block inference. If the photo upload fails, the node queues a text fallback.


## 7. Pi-Owned Audio Output and Volunteer Input Interlock

The Pi sends a `capabilities` message on `/health`, `/ingest`, and the dashboard WebSocket. The portal checks capabilities before requesting browser media permissions. When the Pi reports an ALSA playback interface, the Pi owns audio output and browser microphone/audio-source donation is blocked; a `both` request is reduced to camera-only before `getUserMedia` is called. A microphone-only request is rejected before browser permissions are requested. The Pi also rejects microphone handshakes and `audio_chunk` messages at the node boundary.

The hardware probe uses `aplay -l`: this confirms an ALSA playback interface, not that a speaker transducer is physically plugged in or that sound pressure is safe. On-device wiring and audible output must be checked during Pi commissioning. The portal never generates or plays a deterrence tone; all output generation and playback are owned by the Pi.

## 8. Incident and Deterrence Result Delivery

The node sends canonical incident fields over MQTT or REST, including a `deterrence` object (`attempted`, `started`, `reason`, selected frequency, duration, emission count, and output device). REST remains the fallback if MQTT is unavailable; unsuccessful delivery is retained in the Pi's local SQLite queue, including the deterrence metadata. The Java service persists each attempted deterrence as a `response_events` row attached to the incident and broadcasts the incident to application WebSocket subscribers. Android displays that Pi-reported result in Event History. Telegram is an additional diagnostic notification only.
