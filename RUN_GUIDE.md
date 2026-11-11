# AWARESPAN: Edge Node Run Guide

> **Tagline:** Awareness Without Boundaries.  
> **Official Problem Statement:** An AI-Powered Safety Device.  
> **Project Contact:** awarespan@bchbenjamin.in  
> **Repository:** [https://github.com/awarespan/node-core-processing](https://github.com/awarespan/node-core-processing)

Authoritative operational reference for starting, stopping, verifying, and monitoring the AWARESPAN edge node system.

---

## 1. Network & Port Reference

| Component | Default Port / URL | Description |
|---|---|---|
| Raspberry Pi IP | Configured in environment (`PI_IP`) | Edge processing hardware |
| Node Runtime Stream & Health | `8766` (`/ingest` and `/`) | WebSockets & diagnostic `/health` |
| Local Dashboard | `http://localhost:3000` | Web observation dashboard |
| Backend REST API | Configured in environment (`BACKEND_API_URL`) | Cloud API |
| Central MQTT Broker | Configured in environment (`MQTT_BROKER_URL`) | Outbound telemetry & incident broker |

---

## 2. Managing System Services

On the Raspberry Pi, services run under systemd:

```bash
# Check status of all node components
./scripts/status.sh

# Restart node runtime
sudo systemctl restart awarespan-node.service

# Restart power monitor
sudo systemctl restart awarespan-power-monitor.service

# View live runtime logs
journalctl -u awarespan-node.service -f --no-pager
```

---

## 3. Running Edge Runtime Standalone (Testing / Development)

To run the Node Runtime manually without systemd:

```bash
# From repository root
python3 -m node_runtime.main --port 8766 --conf 0.45
```

The runtime will:
1. Load YOLOv8 weights from `shared/models/yolov8n_best_weapon.pt`.
2. Start the WebSocket server on port `8766`.
3. Connect outbound to the MQTT broker (`sip/{nodeId}/heartbeat`, `sip/{nodeId}/incidents`).
4. Initialize the offline SQLite incident queue (`/tmp/awarespan_event_queue.db`).
5. Process incoming video frames on `/ingest` and broadcast annotated frames on `/`.

---

## 4. Laptop Video Stream Client

To feed laptop webcam frames to the Raspberry Pi:

```bash
# From your laptop
python3 laptop/stream_client.py --pi-host <PI_IP> --port 8766
```

---

## 5. Automated Updates and Rollbacks

The node automatically checks GitHub `main` every 2 minutes. To manage updates manually:

```bash
# 1. Check for remote updates without applying
python3 -m node_manager.cli check

# 2. Trigger staged update immediately
./scripts/update.sh

# 3. Roll back to last verified working revision
./scripts/rollback.sh

# 4. View update history and version state
python3 -m node_manager.cli status
```

---

## 6. Telegram Telemetry & Threat Testing

- Message `/status` to the bot to check thermals, throttled flags, and service health.
- Message `/threats` to see the current classification rules.
- **Upload any photo** to test real-time weapon and threat inference.
