# Raspberry Pi Scripts

Reference guide for all scripts on the Raspberry Pi 5 Edge Compute Core. All scripts live in `node-backend/pi/` and are deployed to the Pi at `192.168.0.125` (WiFi) or `10.42.0.1` (USB gadget).

## Pi Connectivity

| Interface | Address | Use |
|-----------|---------|-----|
| WiFi (wlan0) | `192.168.0.125` | Normal operation |
| USB gadget (usb0) | `10.42.0.1/24` | Recovery / no-network scenarios |

Credentials: <SSH_USERNAME> / <SSH_PASSWORD>

```bash
# SSH onto Pi via WiFi
ssh benjamin@192.168.0.125

# Via USB gadget (no network needed)
ssh benjamin@10.42.0.1
```

---

## Systemd Services

Two services manage long-running processes:

### sip-edge.service — Edge Inference Server
Starts `edge_server.py` on boot. Handles YOLOv8 threat detection via WebSocket.

```bash
# View status
systemctl --user status sip-edge

# View logs
journalctl --user -u sip-edge -f

# Restart
systemctl --user restart sip-edge
```

### sip-power-monitor.service — Power Monitor
Starts `power_monitor.py` on boot. Polls `vcgencmd get_throttled` every 60s and sends ONE Telegram alert after >30 min of continuous undervoltage.

```bash
# View status
systemctl --user status sip-power-monitor

# View logs
journalctl --user -u sip-power-monitor -f

# Restart
systemctl --user restart sip-power-monitor
```

Both services use `Restart=always` and `Nice=5` (low CPU priority so they do not interfere with training).

---

## Dataset Registry

`dataset_registry.py` tracks all datasets persistently in `dataset_registry.json` with atomic JSON writes.

```bash
# View all datasets
python dataset_registry.py --list

# View training-eligible datasets only
python dataset_registry.py --list --status TRAINING_ELIGIBLE

# Get detailed info for a dataset
python dataset_registry.py --show <dataset_id>
```

Current registry (7 datasets):

| ID | Name | Status |
|----|------|--------|
| `roboflow-gun-knife` | Roboflow Gun+Knife Detection | TRAINING_ELIGIBLE |
| `zenodo-nestler` | Zenodo NESTLER Wildlife | TRAINING_ELIGIBLE |
| `kaggle-weapon` | Kaggle Weapon Detection | PENDING_DOWNLOAD |
| `kaggle-pet` | Kaggle Pet Detection | PENDING_DOWNLOAD |
| `tigdog` | TigDog Dataset | PENDING_DOWNLOAD |
| `safari` | Safari Dataset | PENDING_DOWNLOAD |
| `elephants-foxes` | Elephants & Foxes | PENDING_DOWNLOAD |

Dataset classes: `["gun", "knife", "dangerous_animal"]`

---

## Registering New Datasets

Run `register_datasets.py` to pre-populate or refresh the registry with all known datasets:

```bash
python register_datasets.py
```

After adding a new dataset manually, update the registry:

```bash
python dataset_registry.py --register --id my-dataset --name "My Dataset" --source "https://example.com" --license "CC-BY-4.0"
```

---

## Autonomous Training

`train_autonomous.py` runs the 24/7 YOLOv8 training pipeline with manifest verification and checkpoint compatibility checks.

```bash
# Full run with manifest and checkpoint verification
python train_autonomous.py --dataset unified --epochs 150 --device cuda

# Dry-run: verify manifests and checkpoint only (no training)
python train_autonomous.py --dry-run

# Resume from a specific checkpoint
python train_autonomous.py --resume-from runs/train/exp12/weights/best.pt

# Override device
python train_autonomous.py --device cpu
```

The script:
1. Verifies dataset manifest integrity before training
2. Checks that checkpoint class IDs match the current model configuration
3. Falls back to CPU if CUDA is unavailable or OOM detected
4. Runs continuous 150-epoch cycles until stopped

Training output goes to `runs/train/expN/`. Checkpoints: `weights/best.pt`, `weights/last.pt`.

---

## Dataset Audit

`dataset_audit.py` performs forensic validation of the unified dataset:

```bash
# Full audit
python dataset_audit.py

# Audit a specific split
python dataset_audit.py --split train
python dataset_audit.py --split val
```

Audit checks:
- Image decode (all JPG/PNG files readable)
- YOLO label format (class ID in range 0-2, bounding box coords valid)
- Duplicate detection (checksum-based)
- Split leakage (images appearing in both train and val)

Last audit: **PASSED** — 17924 samples, 0 malformed, 0 invalid class.

---

## Power Monitor

`power_monitor.py` monitors undervoltage events and alerts via Telegram.

- Polls `vcgencmd get_throttled` every 60 seconds
- Sends ONE Telegram alert after >30 min continuous undervoltage
- Sends ONE recovery message when power is restored
- Avoids spam by tracking state across invocations

```bash
# Run manually (for testing)
python power_monitor.py --test
```

The systemd service (`sip-power-monitor.service`) ensures it runs on boot and auto-restarts on crash.

---

## Telegram Integration

Two Telegram scripts for remote monitoring:

### telegram_notify.py — Automated Notifications
Sends progress updates during training. Detects IPv4/IPv6 and displays the Pi's network address.

```bash
# Send a test notification
python telegram_notify.py --message "Training started on Pi"

# Send with photo
python telegram_notify.py --message "Epoch 50 complete" --photo runs/train/exp12/results.png
```

Requires `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in the environment.

### telegram_bot.py — Interactive Bot
Interactive Telegram bot that responds to commands and performs on-demand image inference.

```bash
# Start the bot
python telegram_bot.py
```

Commands:
- `/status` — Current system status, training progress, dataset registry summary
- `/incidents` — Recent incidents from the backend
- Send an image — Runs YOLOv8 inference and returns annotated image with detections

---

## MQTT / Backend Communication

The Pi communicates with the backend (`https://api.sip.bchbenjamin.in`) via two channels:

### mqtt_client.py — MQTT Bridge
Publishes detections and incidents to the backend MQTT broker. Subscribes to command topics.

```bash
python mqtt_client.py
```

### backend_sync.py — REST Fallback
When MQTT is unavailable, `backend_sync.py` sends incidents to the backend via REST API as a fallback.

```bash
# Sync pending incidents
python backend_sync.py --sync-incidents

# Check backend health
python backend_sync.py --health-check
```

---

## Dataset Download

`download_and_merge.py` downloads external datasets and merges them into unified YOLO format.

```bash
# Download and merge all pending datasets
python download_and_merge.py --all

# Download a specific dataset
python download_and_merge.py --dataset zenodo-nestler

# Download without merging (separate output dirs)
python download_and_merge.py --dataset kaggle-pet --no-merge
```

---

## Quick Reference

```bash
# Start all services
systemctl --user start sip-edge sip-power-monitor

# Stop all services
systemctl --user stop sip-edge sip-power-monitor

# View all service statuses
systemctl --user list-units 'sip-*'

# Check disk space
df -h

# Check GPU/memory
vcgencmd get_mem gpu && free -h

# View training progress
tail -f runs/train/expN/results.csv

# Force-stop a stuck training
pkill -f train_autonomous
```