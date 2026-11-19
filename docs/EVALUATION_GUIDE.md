# AWARESPAN evaluation guide

AWARESPAN can run the same `node_runtime` software on a Raspberry Pi production node or a general Linux workstation. A workstation can also be explicitly configured to send REST incidents to the production backend for an end-to-end demonstration. The supported software baseline is CPython 3.11 or 3.12 with exact dependency pins and CPU-only PyTorch.

## 1. Prepare a Linux workstation

```bash
./scripts/setup.sh --profile linux
```

The wizard asks whether to install ML training dependencies and whether to connect to production. For an isolated demo, answer no to production. To demonstrate production REST synchronization, answer yes and provide the backend `DEVICE_API_KEY` when prompted. The backend assigns the public node ID and display name during enrollment. Each installation keeps a private installation UUID locally so re-enrollment is idempotent.

The same configuration can be selected without prompts:

```bash
BACKEND_API_KEY="$DEVICE_API_KEY" ./scripts/setup.sh --profile linux --production --no-train --non-interactive
```

Configuration is stored in the repository-root `.env` with mode `0600`, shared by every component and ignored by Git. Production REST sync uses `BACKEND_API_KEY`; MQTT is independent and is not enabled merely by selecting production REST.

## 2. Verify and start the node

```bash
.venv/bin/python ml_pipeline/tools/validate_deployment.py --profile pi5_edge
.venv/bin/python ml_pipeline/tools/smoke_test_models.py
.venv/bin/python -m pytest -q
```

Start terminal 1:

```bash
AWARESPAN_ENV_FILE="$PWD/.env" .venv/bin/python -m node_runtime.main --host 127.0.0.1 --port 8766
```

Start terminal 2:

```bash
.venv/bin/python laptop/stream_client.py --pi-host 127.0.0.1 --pi-port 8766 --camera 0 --fps 8
```

For a phone or another LAN client, bind the runtime to `0.0.0.0`, open the port only on the trusted LAN, and connect to the workstation's LAN IP. Do not expose the runtime directly to the public internet.

## 3. Production backend demonstration

When production REST connectivity was enabled in setup, the runtime uses the configured backend URL and `BACKEND_API_KEY` to enroll. The backend returns the node ID and per-node secret, which are persisted in `.env`; subsequent requests use the per-node credential. Confirm the new workstation node appears in the backend after an actual incident is sent. The backend issues a unique node ID for each installation. Do not share API keys in screenshots, logs or terminal recordings.

A successful REST API sync does not imply MQTT is connected. MQTT needs its own broker URL, credentials and per-node authentication configuration. It also does not validate Pi-specific hardware.

## 4. Raspberry Pi production

When the Pi is available, run the same setup wizard using the Pi profile:

```bash
./scripts/setup.sh --profile pi
```

See [`RASPBERRY_PI_SETUP.md`](RASPBERRY_PI_SETUP.md) for first boot and hardware acceptance.

## 5. What a workstation can and cannot prove

A Linux workstation can demonstrate application startup, local model loading/inference, webcam ingestion, threat assessment, local queueing and explicitly configured production REST synchronization.

It cannot prove Pi boot firmware, ARM64 package compatibility, CSI camera operation, Pi GPIO, `vcgencmd` power monitoring, speaker hardware, Pi thermal behaviour or sustained Pi inference performance. Label those checks as pending until tested on the physical Pi. Keep speaker/siren/deterrence disabled on a workstation.
