#!/usr/bin/env bash
# Fedora workstation fallback: run AWARESPAN locally without Pi hardware or production credentials.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${AWARESPAN_VENV:-${ROOT}/.venv}"
PYTHON="${VENV}/bin/python"
STATE_DIR="${AWARESPAN_FEDORA_STATE_DIR:-${HOME}/.local/state/awarespan-fedora}"
PORT="${AWARESPAN_FEDORA_PORT:-8766}"
HOST="${AWARESPAN_FEDORA_HOST:-127.0.0.1}"

usage() {
  cat <<USAGE
AWARESPAN Fedora fallback

Usage: ./scripts/fedora.sh <command> [arguments]

Commands:
  setup       Install Fedora OS prerequisites and create .venv
  run         Run the node runtime locally (no systemd, Pi hardware, or production credentials)
  camera      Stream this laptop's webcam into the local runtime
  test        Run the automated test suite
  models      Validate model checksums and run CPU inference smoke tests
  demo        Run the local end-to-end detection/queue demonstration
  help        Show this help

Environment overrides:
  AWARESPAN_FEDORA_HOST=127.0.0.1   Runtime bind address (use 0.0.0.0 for LAN clients)
  AWARESPAN_FEDORA_PORT=8766        Runtime WebSocket port
  AWARESPAN_FEDORA_STATE_DIR=...    Local state directory
  AWARESPAN_VENV=...                Python virtual environment path

Start the runtime in one terminal, then run 'camera' in another.
USAGE
}

prepare_env() {
  mkdir -p "$STATE_DIR"
  chmod 700 "$STATE_DIR"
  export AWARESPAN_ENV_FILE="$ROOT/config/fedora.env"
  export PI_NODE_ID="sip-fedora-eval"
  export AWARESPAN_STATE_DIR="$STATE_DIR"
  export OFFLINE_QUEUE_PATH="$STATE_DIR/events.sqlite3"
  export INCIDENT_DB_PATH="$STATE_DIR/events.sqlite3"
  export TOTP_SECRET_FILE="$STATE_DIR/totp_secret.json"
  export DETERRENCE_STATE_FILE="$STATE_DIR/deterrence_state.json"
  export SIREN_FILE="$STATE_DIR/audio/presence_warning.wav"
  export RUNTIME_HOST="$HOST"
  export RUNTIME_PORT="$PORT"
  export SIREN_ENABLED=false SPEAKER_ENABLED=false PRESENCE_DETERRENCE_ENABLED=false
  export AWARESPAN_AUTO_UPDATE_ENABLED=false ML_TRAINING_ENABLED=false
  # Keep the Fedora fallback isolated from the production Pi identity and services.
  if [[ "${AWARESPAN_FEDORA_LIVE_BACKEND:-0}" != "1" ]]; then
    export BACKEND_API_URL= BACKEND_API_KEY= PI_DEVICE_SECRET=
    export MQTT_BROKER_URL= MQTT_USERNAME= MQTT_PASSWORD=
    export ALERT_WEBHOOK_URL=
  fi
}

case "${1:-help}" in
  setup)
    if ! command -v dnf >/dev/null 2>&1; then echo "This setup command expects Fedora/dnf." >&2; exit 2; fi
    sudo dnf install -y python3 python3-devel gcc gcc-c++ make git libgomp mesa-libGL glib2
    python3 -m venv "$VENV"
    "$PYTHON" -m pip install --upgrade pip
    "$PYTHON" -m pip install -r "$ROOT/requirements/dev.txt"
    echo "Fedora environment ready: $VENV"
    ;;
  run)
    shift
    [[ -x "$PYTHON" ]] || { echo "Missing virtualenv. Run: ./scripts/fedora.sh setup" >&2; exit 2; }
    prepare_env
    cd "$ROOT"
    exec "$PYTHON" -m node_runtime.main --host "$HOST" --port "$PORT" "$@"
    ;;
  camera)
    shift
    [[ -x "$PYTHON" ]] || { echo "Missing virtualenv. Run: ./scripts/fedora.sh setup" >&2; exit 2; }
    prepare_env
    cd "$ROOT"
    exec "$PYTHON" "$ROOT/laptop/stream_client.py" --pi-host 127.0.0.1 --pi-port "$PORT" "$@"
    ;;
  test)
    [[ -x "$PYTHON" ]] || { echo "Missing virtualenv. Run: ./scripts/fedora.sh setup" >&2; exit 2; }
    prepare_env
    cd "$ROOT"
    exec "$PYTHON" -m pytest -q
    ;;
  models)
    [[ -x "$PYTHON" ]] || { echo "Missing virtualenv. Run: ./scripts/fedora.sh setup" >&2; exit 2; }
    cd "$ROOT"
    "$PYTHON" ml_pipeline/tools/validate_deployment.py --profile pi5_edge
    exec "$PYTHON" ml_pipeline/tools/smoke_test_models.py
    ;;
  demo)
    [[ -x "$PYTHON" ]] || { echo "Missing virtualenv. Run: ./scripts/fedora.sh setup" >&2; exit 2; }
    prepare_env
    cd "$ROOT"
    exec "$PYTHON" scripts/evaluation_demo.py --test-detection
    ;;
  help|-h|--help) usage ;;
  *) echo "Unknown command: $1" >&2; usage >&2; exit 2 ;;
esac
