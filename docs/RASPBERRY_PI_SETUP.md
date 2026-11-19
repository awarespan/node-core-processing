# Raspberry Pi 5 deployment

This guide covers the production Raspberry Pi 5. The Pi performs inference and device operations only; ML training runs on a workstation.

## 1. Hardware and OS

- Raspberry Pi 5 (4 GB or better), adequate cooling and a suitable power supply.
- microSD card (32 GB or larger recommended).
- **Raspberry Pi OS Desktop (64-bit, Bookworm)**, selected in Raspberry Pi Imager. AWARESPAN pins CPython 3.11 because the deployed PyTorch/torchvision stack has been validated against that interpreter; do not use a Python 3.13/3.15-only installation for this software baseline.

In Imager customisation, set hostname `awarespan-pi`, username `benjamin`, timezone `Asia/Kolkata`, network credentials and SSH public-key authentication. Use a new Linux password; do not reuse any previously exposed password.

The first boot must be completed on the physical Pi. The SD card can be prepared offline, but Fedora cannot certify Pi firmware, first-boot customisation or peripherals.

## 2. First boot and connectivity

1. Insert the flashed card, connect display/keyboard/network and power on.
2. Complete Raspberry Pi OS first-boot setup.
3. On the Pi, verify `uname -m` returns `aarch64`.
4. From Fedora, connect with `ssh benjamin@awarespan-pi.local` (or the Pi's current LAN IP).

## 3. Install the production runtime

Clone the canonical repository and install:

```bash
git clone https://github.com/awarespan/node-core-processing.git
cd node-core-processing
./scripts/setup.sh --profile pi
./scripts/status.sh
```

The wizard detects the Pi, installs the CPython 3.11 venv, CPU-only PyTorch and pinned `requirements/runtime.txt` dependencies, then installs Ultralytics without pulling a second OpenCV distribution. It can install the edge runtime, power monitor and updater systemd services. ML training remains workstation-only. Setup asks whether to configure the optional interactive Telegram bot; when selected on a Pi with services enabled, it installs a separate `awarespan-bot.service`. It also asks whether to connect to production and securely prompts for the backend device API key when needed.

## 4. Configure secrets

Keep one canonical device environment in the repository-root `.env`, copied from `.env.example` and protected with mode `0600`. The node runtime, updater, power monitor and optional Telegram service all read this same file; no `/etc/awarespan/node.env` or `~/.config/awarespan/node.env` copy is created. Existing legacy node.env files are migrated into the root `.env` by setup when needed. Configure:

- `BACKEND_API_URL`
- `PI_NODE_ID` (backend-assigned at enrollment; do not set manually)
- `BACKEND_API_KEY` (the same value configured as `DEVICE_API_KEY` on the backend)
- `PI_DEVICE_SECRET` (optional per-node secret, if the backend node record uses one)
- MQTT broker credentials, if used
- `BOT_TOKEN`, `PRIMARY_CHAT_ID` and/or `ALLOWED_CHAT_IDS` for the optional operator bot

Do not invent credentials, commit environment files, or print secrets in logs. The backend assigns each installation a unique node ID during enrollment; do not manually set `PI_NODE_ID` or `PI_DEVICE_SECRET`.

## 5. Production services

| Unit | Purpose |
|---|---|
| `awarespan-node.service` | Edge inference, threat assessment, communications and runtime WebSocket server |
| `awarespan-power-monitor.service` | Pi power and thermal monitoring |
| `awarespan-updater.timer` / `.service` | Scheduled update checks and controlled updates |

Useful commands:

```bash
./scripts/status.sh
sudo systemctl status awarespan-node.service --no-pager
sudo journalctl -u awarespan-node.service -f
```

The Telegram operator bot remains optional and separate under `pi/telegram_bot/`. Setup asks whether to configure it; when selected, the dedicated service reads the same repository-root `.env` as the node.

## 6. Model artifacts

The Pi loads the committed model files from `shared/models/` using `models/deployed/manifest.json`. Validate the file checksums before deployment:

```bash
python3 ml_pipeline/tools/validate_deployment.py --profile pi5_edge
```

The current person/dog COCO model remains a provisional baseline pending field validation. Keep speaker/siren flags disabled until the physical transducer is installed and acoustically measured.

## 7. Training policy

Do not train models on the production Pi. Dataset acquisition, annotation, training, evaluation and checkpoint promotion belong on a dedicated workstation. Only reviewed, checksummed model artifacts are promoted into `shared/models/`. See [`ml_pipeline/training/README.md`](../ml_pipeline/training/README.md).

## 8. Hardware acceptance still required

When the Pi is available, separately verify actual boot, camera module, microphone, speaker/amplifier, GPIO, power/thermal monitor, MQTT/backend connectivity and sustained inference. Fedora tests are software fallback tests, not proof of Pi hardware operation.
