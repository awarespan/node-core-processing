# Raspberry Pi 5 deployment

This guide covers the production Raspberry Pi 5. The Pi performs inference and device operations only; ML training runs on a workstation.

## 1. Hardware and OS

- Raspberry Pi 5 (4 GB or better), adequate cooling and a suitable power supply.
- microSD card (32 GB or larger recommended).
- **Raspberry Pi OS Desktop (64-bit)**, selected in Raspberry Pi Imager.

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

The wizard detects the Pi, installs `requirements/runtime.txt`, and can install the edge runtime, power monitor and updater systemd services. It does **not** install model training or the optional interactive Telegram bot. It asks whether to connect to production and securely prompts for the backend device API key when needed.

## 4. Configure secrets

Keep the device environment outside Git. The wizard creates a private config in `~/.config/awarespan/node.env` and installs a service-readable copy at `/etc/awarespan/node.env` owned by the node operator for systemd, both protected with mode `0600`. Configure:

- `BACKEND_API_URL`
- `PI_NODE_ID` (production identity: `sip-pi-001`)
- `BACKEND_API_KEY` (the same value configured as `DEVICE_API_KEY` on the backend)
- `PI_DEVICE_SECRET` (optional per-node secret, if the backend node record uses one)
- MQTT broker credentials, if used
- Telegram notification credentials, if notifications are enabled

Do not invent credentials, commit environment files, or print secrets in logs. Only one online device may use `sip-pi-001` at a time.

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

The interactive Telegram bot is a separate temporary tool under `pi/telegram_bot/`; it is not part of the normal install.

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
