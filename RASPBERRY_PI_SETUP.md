# AWARESPAN — Raspberry Pi 5 Setup & Deployment Guide

> **Tagline:** Awareness Without Boundaries.  
> **Official Problem Statement:** An AI-Powered Safety Device.  
> **Project Contact:** awarespan@bchbenjamin.in  
> **Repository:** [https://github.com/awarespan/node-core-processing](https://github.com/awarespan/node-core-processing)

Comprehensive guide for provisioning, deploying, and maintaining an AWARESPAN edge node on Raspberry Pi 5 hardware (4GB RAM).

---

## 1. Hardware Prerequisites

- **Raspberry Pi 5 (4GB RAM)**
- **Official 27W USB-C Power Supply** (vital to prevent undervoltage CPU throttling)
- **microSD card** (≥32GB, Class 10 / A2 rated) or NVMe SSD
- **Active Cooling** (Raspberry Pi active cooler heatsink + fan recommended)
- **Local Network Connectivity** (Ethernet or 5GHz Wi-Fi)

---

## 2. Operating System Preparation

1. Download and launch **[Raspberry Pi Imager](https://www.raspberrypi.com/software/)**.
2. Select **Raspberry Pi 5** and **Raspberry Pi OS Lite (64-bit, Bookworm)**.
3. In OS Customization settings:
   - Configure hostname: `raspberrypi`
   - Enable SSH (public key authentication or strong password)
   - Set username: `benjamin`
   - Configure local Wi-Fi credentials
4. Write to SD card, insert into Pi, and power on.

---

## 3. Cloning Repository on the Pi

Connect via SSH:
```bash
ssh <username>@<pi_ip>
```

Clone the canonical repository directly onto the Pi:
```bash
git clone https://github.com/awarespan/node-core-processing.git
cd node-core-processing
```

---

## 4. One-Step Automated Installation

Run the idempotent installer:
```bash
./scripts/install.sh
```

The installation script automatically handles:
- Installing system dependencies (`libopenblas-dev`, `libgl1`, `git`, `python3-venv`, `curl`).
- Creating persistent directories (`/var/lib/awarespan`, `/var/log/awarespan`, `/var/lock/awarespan`).
- Building the Python virtual environment and installing `requirements/runtime.txt`.
- Initializing the canonical root `.env` from `.env.example`.
- Rendering and installing systemd service and timer units (`awarespan-updater.timer`, `awarespan-node.service`, `awarespan-power-monitor.service`).
- Configuring non-root passwordless restart permissions in `/etc/sudoers.d/awarespan`.
- Starting services and running a diagnostic health verification.

---

## 5. Configuration (`.env`)

Configure node secrets in the single canonical root `.env`:
```bash
nano .env
```

Key configuration parameters:
```env
# Backend REST & Cloud Synchronization
BACKEND_API_URL=https://api.example.com/
BACKEND_API_KEY=your_backend_api_key

# Node Identity
PI_NODE_ID=node-001
PI_DEVICE_SECRET=your_device_secret

# MQTT Broker (outbound connection)
MQTT_BROKER_URL=tcp://broker.hivemq.com:1883
MQTT_CLIENT_ID=sip-pi-001

# Telegram Operator Notifications
BOT_TOKEN=your_telegram_bot_token
PRIMARY_CHAT_ID=your_chat_id
ALLOWED_CHAT_IDS=your_chat_id

# Automated Updates
AWARESPAN_UPDATE_BRANCH=main
AWARESPAN_UPDATE_CHECK_INTERVAL=120
AWARESPAN_AUTO_UPDATE_ENABLED=true

# Model Training (Disabled by default on edge node)
ML_TRAINING_ENABLED=false
```

---

## 6. Service Management & Systemd Units

| Systemd Unit | Type | Role |
|---|---|---|
| `awarespan-updater.timer` | Timer | Triggers update checks every 2 minutes |
| `awarespan-updater.service` | Oneshot | Executes staged git update & selective restart |
| `awarespan-node.service` | Simple | Real-time edge inference, sensor processing & WebSocket server |
| `awarespan-power-monitor.service` | Simple | Monitors hardware undervoltage, thermals & Telegram alerts |
| `awarespan-training.service` | Simple | Isolated training pipeline (disabled on production nodes) |

### Service Control Commands
```bash
# Check status of all AWARESPAN services
./scripts/status.sh

# Restart runtime
sudo systemctl restart awarespan-node.service

# View live runtime logs
journalctl -u awarespan-node.service -f

# View auto-updater logs
journalctl -u awarespan-updater.service -f
```

---

## 7. Verifying Operation

1. **Verify Services:**
   ```bash
   ./scripts/status.sh
   ```
2. **Test Live Threat Detection via Telegram:**
   - Message the Telegram Bot: `/status`
   - Send any test image containing a person or weapon. The bot replies with bounding boxes and threat tiers within seconds.
3. **Trigger Manual Update Check:**
   ```bash
   ./scripts/update.sh
   ```
4. **Trigger Rollback if Needed:**
   ```bash
   ./scripts/rollback.sh
   ```
