# AWARESPAN evaluation guide

AWARESPAN has two execution targets: Raspberry Pi 5 for production edge operation, and Fedora x86-64 for a software evaluation fallback when the Pi is unavailable.

## A. Fedora laptop fallback

The Fedora path runs the same `node_runtime` application and committed model artifacts locally. It uses a separate node identity, local state and no production backend/MQTT credentials by default.

### Prepare

```bash
./scripts/fedora.sh setup
./scripts/fedora.sh models
./scripts/fedora.sh test
```

### Start the node

Terminal 1:

```bash
./scripts/fedora.sh run
```

The local WebSocket runtime listens on `127.0.0.1:8766` by default. It uses `sip-fedora-eval`, stores data under `~/.local/state/awarespan-fedora`, and disables hardware deterrence. It does not connect to production backend or MQTT services unless explicitly configured.

### Send camera frames

Terminal 2:

```bash
./scripts/fedora.sh camera --camera 0 --fps 8
```

This uses the laptop webcam as the camera source and streams frames to the local runtime. For a phone or another LAN client, start the runtime with `AWARESPAN_FEDORA_HOST=0.0.0.0` and connect to the laptop's LAN IP.

### Run a one-shot inference/queue demo

```bash
./scripts/fedora.sh demo
```

This exercises the committed model and local event-queue path using the repository fixture.

## B. Raspberry Pi 5 evaluation

When the Pi is available, complete first boot and install using [`RASPBERRY_PI_SETUP.md`](RASPBERRY_PI_SETUP.md). Use the Pi's own camera, microphone and configured network. Verify model checksums, service health and actual sensor ingestion.

## C. What Fedora can and cannot prove

Fedora can demonstrate application startup, model loading/inference (when ML dependencies are installed), webcam ingestion, threat assessment, local queueing, and API/communications contracts in isolated or explicitly configured test mode.

Fedora cannot prove Raspberry Pi boot firmware, ARM64 package compatibility, CSI camera operation, Pi GPIO, `vcgencmd` power monitoring, speaker hardware, Pi thermal behaviour, or sustained Pi inference performance. Label those checks as pending until tested on the physical Pi.

## D. Safety and credentials

The Fedora profile is deliberately isolated from `sip-pi-001`. Do not reuse the production node identity while the physical Pi may be online. Do not enable speaker/siren output on a laptop. Do not put production credentials in the repository or the committed Fedora profile.
