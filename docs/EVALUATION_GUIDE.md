# AWARESPAN — Evaluator & Field Demonstration Guide

**Project:** AWARESPAN  
**Tagline:** Awareness Without Boundaries.  
**Problem Statement:** An AI-Powered Safety Device.  
**Contact:** awarespan@bchbenjamin.in  
**Evaluation Target:** Raspberry Pi 5 (4 GB RAM)  

---

## 1. Quick Demonstration Workflow (Under 3 Minutes)

This step-by-step procedure guides an evaluator through testing volunteer camera ingestion and real end-to-end knife detection on the edge node without an internet connection.

### Step 1: Verify Node Status & Evaluation Parameters
On the Raspberry Pi terminal (via SSH at `192.168.0.125` or local screen):
```bash
python3 scripts/evaluation_demo.py --summary
```
This outputs the active node IP addresses, volunteer portal URL, and active AI model.

### Step 2: Connect Volunteer Phone to Node
1. On your phone (iPhone, Android, or laptop), connect to the Wi-Fi network:
   - **SSID:** `AWARESPAN-AP` (or the existing local LAN)
   - **Password:** `awarespan123`
2. Open the mobile web browser and navigate to:
   - **Hotspot URL:** `https://192.168.4.1:8443/`  
   - *(or LAN URL if on Ethernet router: `https://192.168.0.125:8443/`)*
3. Acknowledge the self-signed TLS prompt (**Advanced** $\rightarrow$ **Proceed**).

### Step 3: Authenticate with Operator TOTP
1. Retrieve the current 6-digit TOTP code on the Pi terminal:
   ```bash
   python3 scripts/evaluation_demo.py --totp
   ```
2. Enter the displayed 6-digit code on the phone web portal.
3. Select role: **Camera & Microphone** (or **Camera Only**).
4. Tap **Authorize & Connect**.
5. When prompted by the browser, tap **Allow** for Camera and Microphone access.

### Step 4: Verify Source Connection & Telegram Notification
1. Check that the phone screen shows a live video preview and an active frame counter (`Frames sent: ... | Transport: Binary WebSocket`).
2. Verify that Telegram receives a source connection alert:
   ```text
   AWARESPAN | SOURCE CONNECTED
   Node: Raspberry Pi 5
   Source: Camera + Microphone
   Device: Volunteer Device (192.168.4.15)
   Status: Active
   Time: 14:32:18
   ```
   *(If the Pi is operating offline, the notification is held in the SQLite queue and delivered once network connectivity returns).*

### Step 5: Test Weapon Detection (Knife / Gun)
1. Point the volunteer phone camera at a demo knife or test image.
2. Observe the edge node logs or runtime dashboard:
   - YOLOv8 executes local inference on the ingested frame.
   - Bounding boxes identify `knife` with confidence score.
   - Threat assessment evaluates **Tier 2 Critical Weapon Threat**.
   - Deterrence response triggers siren (if enabled) and logs the incident.
   - An incident record is written into the local SQLite database (`state/incidents.db`) with `source_id` properly attributed to the volunteer device!

### Step 6: Disconnect and Verify Lifecycle Teardown
1. On the phone web portal, tap **Disconnect Stream**.
2. Verify that Telegram receives:
   ```text
   AWARESPAN | SOURCE DISCONNECTED
   Node: Raspberry Pi 5
   Source: Camera + Microphone
   Device: Volunteer Device (192.168.4.15)
   Status: Disconnected
   Time: 14:35:10
   ```
3. Verify that the node immediately frees the volunteer slot:
   ```bash
   python3 scripts/evaluation_demo.py --sources
   ```

---

## 2. Automated Offline Ingestion & Inference Test

To verify the complete detection and SQLite queueing pipeline programmatically without needing a physical phone camera on hand:

```bash
python3 scripts/evaluation_demo.py --test-detection
```

This command executes an end-to-end integration test:
1. Loads the default YOLOv8 weapon detection model (`models/yolov8n_weapon.pt`).
2. Generates an authentic `FramePacket` with a synthetic volunteer source ID (`vol-demo-evaluator-01`).
3. Passes the frame through `CoreMediaRouter` and `VisualDetector`.
4. Evaluates the detection through `ThreatAssessor`.
5. Enqueues a `ThreatEvent` into the offline SQLite queue with verified `source_id="vol-demo-evaluator-01"`.
6. Queries the database to confirm immediate persistence.

---

## 3. Troubleshooting & Diagnostics

| Symptom | Probable Cause | Action |
|---|---|---|
| Browser says "Camera access denied" | Accessed via HTTP instead of HTTPS | Ensure URL starts with `https://` (port 8443). Secure context is required. |
| Portal says "Invalid code" | TOTP expired (>30s window) | Run `python3 scripts/evaluation_demo.py --totp` to get a fresh code. |
| Portal says "Too many failed attempts" | Rate-limited after 5 failed tries | Wait 5 minutes for the lockout window to expire. |
| Frames sent counter is 0 | Camera stream not selected or paused | Check browser camera permissions in site settings. |
| Telegram message delayed | Node is currently offline | Expected behavior. Messages queue in `state/telegram_queue.db` and auto-deliver when internet is restored. |
