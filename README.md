# AWARESPAN — Edge Node

AWARESPAN is an edge safety node for media ingestion, visual inference, threat assessment, deterrence control and backend synchronization. Raspberry Pi 5 (64-bit Raspberry Pi OS) is the production target; ordinary Linux workstations can run the same software for development and demonstrations.

## One setup command

Clone the repository, enter it, and run:

```bash
./scripts/setup.sh
```

The setup wizard detects Raspberry Pi hardware versus a general Linux machine and asks whether to install ML training dependencies, connect to the production backend, and (on a Pi) install system services. The dependency baseline is CPython 3.11 with exact package pins. The installer replaces an incompatible existing virtual environment, installs the CPU-only PyTorch 2.5.1 / torchvision 0.20.1 pair first, and refuses source builds. Selecting ML training installs the complete development/test stack plus the dedicated dataset/training packages, and writes the dataset, checkpoint and deployment-manifest paths into the private node configuration. Safe defaults are used: production connectivity and training are off unless selected. The script creates a private configuration file outside Git.

The same choices are available as flags for automation:

```bash
# Raspberry Pi production install (interactive credentials if needed)
./scripts/setup.sh --profile pi --no-train --production --service

# Fedora/Ubuntu workstation, production API enabled, no training
BACKEND_API_KEY="$DEVICE_API_KEY" ./scripts/setup.sh --profile linux --production --no-train --non-interactive

# Workstation prepared for ML training, isolated from production
./scripts/setup.sh --profile linux --train --no-production
```

Secrets must never be passed as command-line arguments. For non-interactive setup, export `BACKEND_API_KEY` (the backend's `DEVICE_API_KEY`) and optionally `PI_DEVICE_SECRET` in the environment. Interactive setup prompts for the API key with hidden input. The resulting config is stored at `/etc/awarespan/node.env` on a Pi or `~/.config/awarespan/node.env` on another Linux host, with mode `0600`.

See [`scripts/README.md`](scripts/README.md) for all flags and [`docs/EVALUATION_GUIDE.md`](docs/EVALUATION_GUIDE.md) for a workstation demo.

## Run on a Linux workstation

After setup, start the node in terminal 1 (replace the config path if you selected a custom `--env-file`):

```bash
AWARESPAN_ENV_FILE="$HOME/.config/awarespan/node.env" .venv/bin/python -m node_runtime.main --host 127.0.0.1 --port 8766
```

In terminal 2, send webcam frames to it:

```bash
.venv/bin/python laptop/stream_client.py --pi-host 127.0.0.1 --pi-port 8766 --camera 0 --fps 8
```

For a phone or another LAN client, bind the runtime to `0.0.0.0`, allow the port through the host firewall, and use the workstation's LAN IP. Do not expose the runtime directly to the public internet.

A Linux workstation can connect to production REST APIs when explicitly configured. Use a distinct node ID such as `sip-fedora-eval`; never run two devices concurrently with the same `sip-pi-001` identity. Production REST API authentication uses the backend `DEVICE_API_KEY`, stored locally as `BACKEND_API_KEY`. MQTT is a separate integration and remains unconfigured unless its broker settings and per-node credentials are supplied.

## Raspberry Pi production

Use a 64-bit Raspberry Pi OS image whose repositories provide CPython 3.11 (the validated baseline is Raspberry Pi OS Bookworm), complete first boot, clone this repository and run `./scripts/setup.sh`. The Pi profile installs runtime dependencies and can install the production systemd services. It never installs ML training dependencies. See [`docs/RASPBERRY_PI_SETUP.md`](docs/RASPBERRY_PI_SETUP.md).

## Architecture

```text
node_runtime/       Production inference and edge application logic (no training)
node_manager/       Health checks, update orchestration and rollback
shared/             Runtime configuration, event models, logging and utilities
shared/models/      Versioned deployment weights used by Pi and Linux workstations
models/             Deployment manifest, checksums and model registry
pi/                 Raspberry Pi launchers and optional temporary Telegram bot
ml_pipeline/        Workstation-side datasets, training, evaluation and packaging
datasets/           Small committed fixtures/manifests; private datasets stay external
deployment/         Raspberry Pi systemd and sudoers templates
scripts/            Setup wizard and operator commands
laptop/             Webcam sender for Linux workstation demonstrations
static/             Volunteer portal assets
docs/               Project and deployment documentation
```

## Models and ML lifecycle

The committed deployment weights are in `shared/models/`; `models/deployed/manifest.json` declares their paths and SHA-256 checksums. Validate them with:

```bash
.venv/bin/python ml_pipeline/tools/validate_deployment.py --profile pi5_edge
.venv/bin/python ml_pipeline/tools/smoke_test_models.py
```

The smoke test loads the actual weights and performs local inference; it requires the runtime ML dependencies and can be slow on CPU. Training is a separate, explicit workstation workflow. Installing training dependencies does not mean a dataset is ready or a training job is approved. See [`ml_pipeline/README.md`](ml_pipeline/README.md).

## Tests

```bash
.venv/bin/python -m pytest -q
```

Software tests on a workstation do not verify Pi boot, CSI camera, GPIO, audio hardware, thermal/power behaviour or sustained ARM inference. Those checks require the physical Pi.

## Secrets and local state

Never commit `.env`, `node.env`, API keys, device secrets, bot tokens, MQTT credentials, TOTP secrets or SSH credentials. Keep local configuration under `/etc/awarespan/` or `~/.config/awarespan/` with restrictive permissions. Training datasets, caches and run outputs should remain outside Git unless explicitly reviewed for publication.
