# AWARESPAN — Temporary Volunteer Camera Portal

> *A modular, lightweight, temporary web application for authorized operator devices to volunteer camera input to an AWARESPAN Raspberry Pi edge node. The Pi owns local audio output; browser microphone donation is disabled until a real Pi-side input pipeline is commissioned.*

---

## 1. Architectural Philosophy

* **Sole Backend:** The Raspberry Pi edge node running `node-core-processing` (`node-backend`) is the authoritative backend. No intermediary cloud servers, databases, or API gateways are introduced.
* **Separation of Concerns:** The frontend performs **zero AI threat detection**. Frames are encoded and transmitted directly to the Pi's WebSocket ingestion endpoint (`/ingest`), where YOLOv8 inference and threat assessment execute.
* **Strict Security:** No persistent passwords, TOTP secrets, or Telegram bot tokens exist in the frontend code or browser `localStorage`. Credentials are held as ephemeral in-memory sessions with automatic expiration.
* **Temporary Nature:** The interface is engineered as an isolated, standalone client that can be retired cleanly when dedicated camera/mic hardware is connected to the Pi.

---

## 2. Design Compliance

The application strictly implements the design system documented in the primary website specification (`landing-page/docs/DESIGN.md`):

* **Color Palette:**
  * **Ember Orange (`#ff4f2b`):** CTAs, active toggles, focal alerts.
  * **Void Black (`#000000`):** Core background canvas and media viewport.
  * **Carbon (`#1a1a1a`):** Modular panels and input backgrounds.
  * **Graphite (`#3c3c3c`):** 1px structural hairlines and dividers.
  * **Steel Mid (`#737373`):** Metadata, secondary readouts, timestamps.
  * **Bone White (`#f5f5f5`):** Primary headings, labels, and text.
* **Geometry:** **`0px` border-radius** on all buttons, inputs, badges, and cards.
* **Typography:** `Chivo Mono` & `JetBrains Mono` for a terminal/control-room aesthetic.

---

## 3. Verified Raspberry Pi Node Interfaces

Inspection of `node-backend` (`origin https://github.com/awarespan/node-core-processing.git`) identified:

* **Port:** `8766` (Configurable via `RUNTIME_PORT`).
* **Health Probe:** `ws://<pi_host>:8766/health` &rarr; responds with node ID and Pi audio/input capabilities, then closes.
* **Visual Frame Ingest:** `ws://<pi_host>:8766/ingest` &rarr; accepts JSON packets matching `{ type: "frame", frame_id, ts_ms, jpeg_b64 }`.
* **Dashboard Stream:** `ws://<pi_host>:8766/` &rarr; broadcasts annotated frames and threat evaluation logs.

*See [`BACKEND_CONTRACT.md`](./BACKEND_CONTRACT.md) for the integration contract, Pi-owned audio interlock, and evidence feed.*

---

## 4. Getting Started & Development

### Prerequisites
* Node.js v20+ or v22+
* npm v10+

### Installation
```bash
cd temp_frontend
npm install
```

### Environment Configuration
Copy the template configuration:
```bash
cp .env.example .env
```

| Variable | Default | Description |
| :--- | :--- | :--- |
| `VITE_PI_HOST` | `192.168.1.50` | Hostname or IP of Raspberry Pi edge node |
| `VITE_PI_PORT` | `8766` | Node runtime WebSocket port |
| `VITE_PI_USE_SSL` | `false` | Set `true` for WSS / HTTPS |
| `VITE_PI_NODE_ID` | `sip-pi-001` | Edge node identifier |
| `VITE_MOCK_MODE` | `true` in dev | High-fidelity hardware simulation mode |

### Running the Development Server
```bash
npm run dev
```
Open `http://localhost:3000` in any modern browser.

### Running Test Suite
Execute the 17 mandatory lifecycle tests and UI component tests:
```bash
npm run test
```

### Production Build
```bash
npm run build
```
Build output is generated into the `dist/` directory.

---

## 5. 17 Mandatory Verification Scenarios

The portal's Vitest test suite (`tests/all-17-requirements.test.ts`) verifies:

1. **Successful Authentication:** Validates operator TOTP and issues short-lived session token.
2. **Failed Authentication:** Rejects invalid format or bad TOTP code without session issue.
3. **Camera Permission Granted:** Initializes local stream and starts canvas capture loop.
4. **Camera Permission Denied:** Detects `NotAllowedError` and enters `PERMISSION_DENIED`.
5. **Pi Audio Ownership:** Checks Pi capabilities before requesting browser permissions; the portal never plays deterrence audio.
6. **Microphone Input Disabled:** Production microphone donation is blocked until the Pi advertises a working input pipeline; mock-mode tests can still simulate the UI.
7. **Camera-Only Volunteering:** Transmits video frames and receives camera source ACK.
8. **Microphone-Only Volunteering:** Refuses before browser permission unless the Pi explicitly advertises an operational microphone input path.
9. **Combined Volunteering:** Degrades to camera-only when the Pi has not advertised a supported microphone input path.
10. **Pi Rejects Connection:** Correctly captures rejection message (e.g. node capacity exceeded).
11. **Pi Becomes Unreachable:** Detects connection failure and alerts operator.
12. **Browser Tab Closes:** Immediately ends all hardware streams and closes sockets.
13. **User Manually Stops:** Explicit halt releases camera/mic hardware LEDs and sends stop packet.
14. **Network Changes:** Detects `offline` network transition and pauses transmission.
15. **Auto-Reconnection:** Executes exponential backoff to recover from temporary glitches.
16. **Session Expiration:** Detects expired session token and halts active volunteer media capture.
17. **Hardware Stream Release:** Confirms all media tracks are ended so camera/mic LEDs turn off.

## 6. Test Sound & Detection Evidence

* **Pi-Owned Deterrence:** The Pi generates the bounded warning tone locally. The selected pitch and actual playback-start result are included in the incident payload, persisted in `response_events`, and delivered to the Android application. Telegram is diagnostic only.
* **Detection Evidence:** Subscribes to the Pi's read-only dashboard WebSocket and pairs a threat event with the corresponding Pi-generated annotated JPEG by source and frame ID. The image is downloadable from the portal.
* **Telegram Evidence:** The Pi sends the annotated detection image through Telegram `sendPhoto`, with event ID, labels and confidence in the caption. Inference does not wait for Telegram delivery.


## 7. Audio and Incident Delivery Ownership

The Raspberry Pi is the sole audio-output owner. The temporary website has no local deterrence playback controls. It reads the Pi's advertised ALSA capability and does not request microphone permissions; the current node has no working volunteer microphone-ingestion path, so audio donation is disabled in production. The Pi records each attempted warning in the incident metadata and sends it over MQTT or REST, with a local SQLite retry queue. The backend writes the outcome to `response_events`, includes response events in incident list/detail responses, and pushes the incident to authenticated Android WebSocket subscribers. The Android Event History and Incident Detail screens display the actual Pi-reported result. Telegram is an additional diagnostic channel, not the product delivery path.
