# AWARESPAN — Edge Node

AWARESPAN is an edge safety node for multimodal media ingestion, visual inference, threat assessment, deterrence control and backend synchronization. The production target is Raspberry Pi 5 (64-bit Raspberry Pi OS).

## Architecture

```text
node_runtime/       Production inference and edge application logic (no training)
node_manager/       Health checks, update orchestration and rollback
shared/             Runtime configuration, event models, logging and utilities
shared/models/      Versioned deployment weights used by Pi and Fedora
models/             Deployment manifest, checksums and model registry
pi/                 Raspberry Pi launchers and operator-only integrations
pi/telegram_bot/    Temporary, optional interactive Telegram bot (not auto-enabled)
ml_pipeline/        Workstation-side ML datasets, training, evaluation and packaging
datasets/           Small committed fixtures/manifests; large private datasets stay external
deployment/         Production Raspberry Pi systemd and sudoers templates
scripts/            Small operator command surface
laptop/             Webcam sender used by the Fedora fallback
static/             Volunteer portal assets

docs/               All project and deployment documentation
```

## Choose your environment

### Raspberry Pi 5 — production

After Raspberry Pi OS Desktop 64-bit has completed first boot:

```bash
./scripts/install.sh
./scripts/status.sh
```

The Pi performs inference and device operations only. **Model training is not installed or started by the production installer.** The interactive Telegram bot is optional and separate.

See [Pi deployment instructions](docs/RASPBERRY_PI_SETUP.md) and [Pi entrypoints](pi/README.md).

### Fedora laptop — evaluation fallback

This runs the node runtime locally without Raspberry Pi hardware, systemd, or production credentials by default:

```bash
./scripts/fedora.sh setup
./scripts/fedora.sh models
./scripts/fedora.sh test
```

Terminal 1 — start the local node:

```bash
./scripts/fedora.sh run
```

Terminal 2 — stream the laptop webcam into it:

```bash
./scripts/fedora.sh camera --camera 0 --fps 8
```

The local profile uses the distinct node ID `sip-fedora-eval`, stores state under `~/.local/state/awarespan-fedora`, and disables backend/MQTT credentials by default. It is a software evaluation fallback, not proof of Pi boot, GPIO, camera-module, power-monitor or acoustic hardware behaviour. For LAN camera clients, set `AWARESPAN_FEDORA_HOST=0.0.0.0` before starting the runtime.

See [evaluation guide](docs/EVALUATION_GUIDE.md).

## Model weights

Committed deployment artifacts live in `shared/models/`. Their paths and SHA-256 checksums are declared in `models/deployed/manifest.json`. Verify them with:

```bash
./scripts/fedora.sh models
```

## ML training

Training is a separate workstation workflow under `ml_pipeline/training/`; it is not part of the Pi runtime or Pi installation. Install `requirements/training.txt` on a dedicated workstation. Only promote validated weights into `shared/models/` and update the deployment manifest.

See [ML pipeline documentation](ml_pipeline/README.md).

## Configuration and secrets

Copy `.env.example` to a secure external configuration location. Never commit `.env`, bot tokens, device secrets, MQTT credentials, TOTP secrets or SSH credentials. The Fedora fallback uses the committed, credential-free `config/fedora.env` profile and does not load production `.env` values.

## Tests

```bash
./scripts/fedora.sh test
./scripts/fedora.sh models
```

Tests on Fedora verify host-side software only. Physical Pi and peripheral checks must be performed when the hardware is available.
