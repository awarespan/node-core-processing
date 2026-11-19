# Operator scripts

Run scripts from any working directory; each resolves the repository root itself.

## Unified setup wizard

`./scripts/setup.sh` is the supported entrypoint for Raspberry Pi and general Linux hosts. It detects hardware/OS, installs host packages and Python dependencies, writes a private environment file, and optionally enables production REST connectivity. On a workstation, `--train` installs both `requirements/dev.txt` and `requirements/training.txt`; the latter includes the full runtime stack and the training/data/evaluation packages. The generated config includes `ML_TRAINING_ENABLED`, `ML_DATASET_DIR`, `ML_CHECKPOINT_DIR` and `ML_DEPLOYMENT_MANIFEST`. It asks questions by default; use flags for repeatable automation.

| Flag | Meaning |
|---|---|
| `--profile auto|pi|linux` | Detect automatically or force a target profile |
| `--train` / `--no-train` | Install or omit workstation ML training dependencies |
| `--production` / `--no-production` | Enable or disable production backend REST sync |
| `--service` / `--no-service` | Install/start Pi systemd services; Pi profile only |
| `--node-id ID` | Set this machine's unique node identity |
| `--backend-url URL` | Override the production backend URL |
| `--env-file PATH` | Choose the private configuration path |
| `--non-interactive` | Disable prompts; only explicitly selected options are enabled |

Secrets are not accepted as command-line arguments. Interactive production setup asks for the backend's `DEVICE_API_KEY` with hidden input. Automation should export `BACKEND_API_KEY` and optionally `PI_DEVICE_SECRET` before running setup. The script stores these in the private env file with mode `0600`.

Examples:

```bash
./scripts/setup.sh
./scripts/setup.sh --profile pi --no-train --production --service
BACKEND_API_KEY="$DEVICE_API_KEY" ./scripts/setup.sh --profile linux --production --no-train --non-interactive
./scripts/setup.sh --profile linux --train --no-production
```

A workstation should use a distinct ID (default `sip-fedora-eval`) rather than impersonating `sip-pi-001`. Production REST authentication uses the shared backend `DEVICE_API_KEY` as `BACKEND_API_KEY`. MQTT remains separate and requires its own broker configuration and node credentials.

## Other operator commands

| Script | Purpose | Target |
|---|---|---|
| `status.sh` | Inspect installed services and node health | Raspberry Pi |
| `update.sh` / `rollback.sh` | Manage a deployed node revision | Raspberry Pi |
| `uninstall.sh` | Remove deployed services (optional `--purge`) | Raspberry Pi |
| `evaluation_demo.py` | Run fixture-based local evaluation | Linux workstation |

Specialist tools live under `pi/`, `tools/` and `ml_pipeline/tools/`.
