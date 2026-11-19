# Raspberry Pi executables

This directory contains **operator entrypoints for the deployed Raspberry Pi**. The application implementation lives in `node_runtime/`; these scripts provide stable, readable commands to launch it.

## Production services

- `./pi/run-node.sh` — starts `node_runtime.main`, the edge inference and decision runtime.
- `./pi/run-power-monitor.sh` — starts the Pi power/thermal monitor.

The supported installer is `./scripts/setup.sh --profile pi`. It installs runtime dependencies and optionally the node runtime, power monitor and updater services. It never installs ML training or the optional Telegram bot.

## Optional temporary Telegram bot

`telegram_bot/` contains the interactive Telegram command bot. It is a temporary operator convenience, not a dependency of inference or the core node. It is **not enabled by default**. See [`telegram_bot/README.md`](telegram_bot/README.md) if it is explicitly needed.

## What does not belong here

Model training, dataset downloads, dataset registration and batch evaluation belong under `ml_pipeline/`. Shared runtime logic belongs under `node_runtime/`. Documentation belongs under `docs/`.

## First boot

After Raspberry Pi OS Desktop 64-bit has completed first boot, install the runtime with:

```bash
./scripts/setup.sh --profile pi
./scripts/status.sh
```

Do not run training on the production Pi. Model weights are deployed from `shared/models/` and verified against `models/deployed/manifest.json`.
