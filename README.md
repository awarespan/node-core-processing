# AWARESPAN — Edge Node

AWARESPAN is an edge safety node for media ingestion, visual inference, threat assessment, deterrence control and backend synchronization. Raspberry Pi 5 (64-bit Raspberry Pi OS) is the production target; ordinary Linux workstations can run the same software for development and demonstrations.

## One setup command

Clone the repository, enter it, and run:

```bash
./scripts/setup.sh
```

The setup wizard detects Raspberry Pi hardware versus a general Linux machine and asks whether to install ML training dependencies, connect to the production backend, install Pi system services, and configure the optional Telegram operator bot. The dependency baseline is CPython 3.11 with exact package pins. The installer replaces an incompatible existing virtual environment, installs the CPU-only PyTorch 2.5.1 / torchvision 0.20.1 pair first, and refuses source builds. Selecting ML training installs the complete development/test stack plus the dedicated dataset/training packages. All components use the same sectioned root `.env`, created from `.env.example` and protected with mode `0600`. Safe defaults are used: production connectivity, training and Telegram remain off unless selected.

The same choices are available as flags for automation:

```bash
# Raspberry Pi production install (interactive credentials if needed)
./scripts/setup.sh --profile pi --no-train --production --service

# Fedora/Ubuntu workstation, production API enabled, no training
BACKEND_API_KEY="$DEVICE_API_KEY" ./scripts/setup.sh --profile linux --production --no-train --non-interactive

# Workstation prepared for ML training, isolated from production
./scripts/setup.sh --profile linux --train --no-production

# Opt in to the separate Telegram operator bot on a Pi
./scripts/setup.sh --profile pi --production --service --telegram-bot
```

Secrets must never be passed as command-line arguments. For non-interactive setup, export `BACKEND_API_KEY` (the backend's `DEVICE_API_KEY`) and optionally `PI_DEVICE_SECRET` in the environment. Interactive setup prompts for the API key with hidden input. The resulting config is stored in the repository-root `.env`, with mode `0600`.

See [`scripts/README.md`](scripts/README.md) for all flags and [`docs/EVALUATION_GUIDE.md`](docs/EVALUATION_GUIDE.md) for a workstation demo.

## Run on a Linux workstation

After setup, start the node in terminal 1 (replace the config path if you selected a custom `--env-file`):

```bash
AWARESPAN_ENV_FILE="$PWD/.env" .venv/bin/python -m node_runtime.main --host 127.0.0.1 --port 8766
```

In terminal 2, send webcam frames to it:

```bash
.venv/bin/python laptop/stream_client.py --pi-host 127.0.0.1 --pi-port 8766 --camera 0 --fps 8
```

For a phone or another LAN client, bind the runtime to `0.0.0.0`, allow the port through the host firewall, and use the workstation's LAN IP. Do not expose the runtime directly to the public internet.

A Linux workstation can connect to production REST APIs when explicitly configured. The backend assigns each installation its own public node ID and display name during enrollment; nodes cannot select either value. The global `DEVICE_API_KEY` is stored locally as `BACKEND_API_KEY` and used only for enrollment. The backend returns the node ID and per-node secret; subsequent REST calls use that credential. MQTT is a separate integration and requires broker configuration.

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
./scripts/test.sh all
```

Re-run just the setup/dependency-selection checks with `./scripts/test.sh setup`. See [`tests/README.md`](tests/README.md) for the test-suite layout.

Software tests on a workstation do not verify Pi boot, CSI camera, GPIO, audio hardware, thermal/power behaviour or sustained ARM inference. Those checks require the physical Pi.

## Secrets and local state

The single canonical configuration is the repository-root `.env`, created from [`.env.example`](.env.example) by the setup wizard. It is shared by the node runtime, ML training tools, Telegram operator bot, MQTT and systemd services. Keep `.env` at mode `0600`; it is ignored by Git. Never commit API keys, device secrets, bot tokens, MQTT credentials, TOTP secrets or SSH credentials. `AWARESPAN_ENV_FILE` can explicitly point a process at that same file when launched outside the repository working directory. Training datasets, caches and run outputs should remain outside Git unless explicitly reviewed for publication.
