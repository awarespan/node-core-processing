#!/usr/bin/env bash
# AWARESPAN unified setup for Raspberry Pi and general Linux workstations.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${AWARESPAN_VENV:-$ROOT/.venv}"
PYTHON="${VENV}/bin/python"
PYTHON_BOOTSTRAP="${AWARESPAN_PYTHON_BIN:-python3.11}"
PYTHON_MINOR="3.11"
PROFILE="auto"
TRAIN=""
PRODUCTION=""
SERVICE=""
TELEGRAM_BOT=""
NON_INTERACTIVE=0
NODE_ID=""
BACKEND_URL="https://api.awarespan.bchbenjamin.in"
ENV_TARGET=""

usage() {
  cat <<'USAGE'
AWARESPAN setup

Usage:
  ./scripts/setup.sh [options]

Requires CPython 3.11 (the version pinned by the model/test matrix). The installer
uses python3.11 explicitly and never falls back to the system python3.

Interactive by default: detects Raspberry Pi vs Linux and asks about ML training,
production backend connectivity and (on a Pi) system services.

Options:
  --profile auto|pi|linux     Override host detection (default: auto)
  --train / --no-train        Install workstation ML training dependencies
  --production / --no-production
                              Connect this node to the production backend
  --service / --no-service    Install/start Pi systemd services (Pi only)
  --telegram-bot / --no-telegram-bot
                              Configure the optional interactive Telegram bot
  --node-id ID                Node identity (default: sip-pi-001 on Pi,
                              sip-fedora-eval on other Linux)
  --backend-url URL           Backend base URL
  --env-file PATH             Write private node configuration to PATH
  --non-interactive           Do not prompt; defaults are safe/off unless flags set
  -h, --help                  Show this help

Secrets are never accepted as command-line arguments. For automation, export
BACKEND_API_KEY and optionally PI_DEVICE_SECRET before invoking this script.
For an interactive production setup, the API key is requested with hidden input.

Examples:
  ./scripts/setup.sh
  ./scripts/setup.sh --profile linux --production --no-train
  BACKEND_API_KEY="$DEVICE_API_KEY" ./scripts/setup.sh --production --non-interactive
  ./scripts/setup.sh --profile linux --train --no-production

The production backend key is the backend's DEVICE_API_KEY. It is stored in the
root .env file as BACKEND_API_KEY. The same .env is shared by runtime, ML,
Telegram and other components; do not commit it.
USAGE
}

ask_yes_no() {
  local prompt="$1" default="$2" answer
  if [[ "$NON_INTERACTIVE" == 1 ]]; then
    [[ "$default" == "yes" ]]
    return
  fi
  while true; do
    if [[ "$default" == "yes" ]]; then
      read -r -p "$prompt [Y/n]: " answer || answer=""
      answer="${answer:-y}"
    else
      read -r -p "$prompt [y/N]: " answer || answer=""
      answer="${answer:-n}"
    fi
    case "$answer" in
      [Yy]|[Yy][Ee][Ss]) return 0 ;;
      [Nn]|[Nn][Oo]) return 1 ;;
      *) echo "Please answer yes or no." ;;
    esac
  done
}

while (($#)); do
  case "$1" in
    --profile) PROFILE="${2:?Missing value for --profile}"; shift 2 ;;
    --train) TRAIN=yes; shift ;;
    --no-train) TRAIN=no; shift ;;
    --production) PRODUCTION=yes; shift ;;
    --no-production) PRODUCTION=no; shift ;;
    --service) SERVICE=yes; shift ;;
    --no-service) SERVICE=no; shift ;;
    --telegram-bot) TELEGRAM_BOT=yes; shift ;;
    --no-telegram-bot) TELEGRAM_BOT=no; shift ;;
    --node-id) NODE_ID="${2:?Missing value for --node-id}"; shift 2 ;;
    --backend-url) BACKEND_URL="${2:?Missing value for --backend-url}"; shift 2 ;;
    --env-file) ENV_TARGET="${2:?Missing value for --env-file}"; shift 2 ;;
    --non-interactive) NON_INTERACTIVE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ "$PROFILE" == auto || "$PROFILE" == pi || "$PROFILE" == linux ]] || { echo "Invalid profile: $PROFILE" >&2; exit 2; }
OS="$(uname -s)"
ARCH="$(uname -m)"
[[ "$OS" == Linux ]] || { echo "AWARESPAN setup currently supports Linux only (detected $OS)." >&2; exit 2; }
MODEL=""
if [[ -r /proc/device-tree/model ]]; then MODEL="$(tr -d '\000' </proc/device-tree/model)"; fi
IS_PI=0
if [[ "$MODEL" == *Raspberry*Pi* || "$MODEL" == *Raspberry*Compute* ]]; then IS_PI=1; fi
if [[ "$PROFILE" == auto ]]; then
  if [[ "$IS_PI" == 1 ]]; then PROFILE=pi; else PROFILE=linux; fi
fi
if [[ "$PROFILE" == pi && "$IS_PI" != 1 ]]; then
  echo "Warning: --profile pi was selected but this host does not identify as a Raspberry Pi."
fi
if [[ "$PROFILE" == pi ]]; then
  DEFAULT_NODE_ID="sip-pi-001"
  DEFAULT_TRAIN=no
  DEFAULT_SERVICE=yes
  DEFAULT_ENV="$ROOT/.env"
  STATE_DIR="/var/lib/awarespan"
else
  DEFAULT_NODE_ID="sip-fedora-eval"
  DEFAULT_TRAIN=no
  DEFAULT_SERVICE=no
  DEFAULT_ENV="$ROOT/.env"
  STATE_DIR="$HOME/.local/state/awarespan"
fi
NODE_ID="${NODE_ID:-$DEFAULT_NODE_ID}"
ENV_TARGET="${ENV_TARGET:-$DEFAULT_ENV}"

# Identify a legacy config before preflight so non-interactive setup can reuse
# credentials already stored in an older installation's file.
LEGACY_ENV_SOURCE=""
if [[ "$ENV_TARGET" == "$ROOT/.env" && ! -f "$ENV_TARGET" ]]; then
  for candidate in \
    "$HOME/.config/awarespan/node.env" \
    "$HOME/.awarespan/node.env" \
    "/etc/awarespan/node.env" \
    "/var/lib/awarespan/node.env" \
    "$HOME/edge-ai/.env"; do
    if [[ -f "$candidate" ]]; then
      LEGACY_ENV_SOURCE="$candidate"
      break
    fi
  done
fi

if [[ "$PRODUCTION" == yes && "$NON_INTERACTIVE" == 1 && -z "${BACKEND_API_KEY:-}" ]]; then
  EXISTING_KEY=""
  KEY_SOURCE="$ENV_TARGET"
  [[ -f "$KEY_SOURCE" ]] || KEY_SOURCE="$LEGACY_ENV_SOURCE"
  if [[ -n "$KEY_SOURCE" && -f "$KEY_SOURCE" ]]; then
    EXISTING_KEY="$(grep -m1 '^BACKEND_API_KEY=' "$KEY_SOURCE" | cut -d= -f2- || true)"
  fi
  if [[ -z "$EXISTING_KEY" ]]; then
    echo "Non-interactive production setup requires BACKEND_API_KEY in the environment or existing env file." >&2
    echo "Export the backend DEVICE_API_KEY and re-run. The secret is never accepted as a CLI argument." >&2
    exit 2
  fi
fi

echo "AWARESPAN setup"
echo "  OS / architecture : $OS / $ARCH"
echo "  Hardware          : ${MODEL:-Generic Linux host}"
echo "  Selected profile  : $PROFILE"
echo "  Node identity     : $NODE_ID"

if [[ -z "$TRAIN" ]]; then
  if [[ "$PROFILE" == pi ]]; then
    TRAIN=no
    echo "ML training is disabled on Raspberry Pi. Production Pi nodes are inference-only."
  elif ask_yes_no "Install ML training dependencies on this machine?" "$DEFAULT_TRAIN"; then TRAIN=yes; else TRAIN=no; fi
fi
if [[ -z "$PRODUCTION" ]]; then
  if ask_yes_no "Connect this node to the AWARESPAN production backend?" no; then PRODUCTION=yes; else PRODUCTION=no; fi
fi
if [[ -z "$SERVICE" ]]; then
  if [[ "$PROFILE" == pi ]]; then
    if ask_yes_no "Install and start the Raspberry Pi systemd services?" "$DEFAULT_SERVICE"; then SERVICE=yes; else SERVICE=no; fi
  else SERVICE=no
  fi
fi
if [[ -z "$TELEGRAM_BOT" ]]; then
  if ask_yes_no "Configure the optional interactive Telegram operator bot?" no; then TELEGRAM_BOT=yes; else TELEGRAM_BOT=no; fi
fi
if [[ "$TRAIN" == yes && ( "$PROFILE" == pi || "$ARCH" == aarch64 || "$ARCH" == arm64 || "$ARCH" == armv7l || "$ARCH" == armv6l ) ]]; then
  echo "ML training is restricted to x86-64 workstations; ARM edge devices are inference-only." >&2
  exit 2
fi
if [[ "$SERVICE" == yes && "$PROFILE" != pi ]]; then
  echo "System service installation is reserved for the Raspberry Pi profile." >&2
  exit 2
fi
if [[ "$TELEGRAM_BOT" == yes && "$NON_INTERACTIVE" == 1 ]]; then
  EXISTING_BOT_TOKEN="${BOT_TOKEN:-}"
  EXISTING_PRIMARY_CHAT="${PRIMARY_CHAT_ID:-}"
  EXISTING_ALLOWED_CHATS="${ALLOWED_CHAT_IDS:-}"
  TELEGRAM_CONFIG_SOURCE="$ENV_TARGET"
  [[ -f "$TELEGRAM_CONFIG_SOURCE" ]] || TELEGRAM_CONFIG_SOURCE="$LEGACY_ENV_SOURCE"
  if [[ -n "$TELEGRAM_CONFIG_SOURCE" && -f "$TELEGRAM_CONFIG_SOURCE" ]]; then
    [[ -n "$EXISTING_BOT_TOKEN" ]] || EXISTING_BOT_TOKEN="$(grep -m1 '^BOT_TOKEN=' "$TELEGRAM_CONFIG_SOURCE" | cut -d= -f2- || true)"
    [[ -n "$EXISTING_PRIMARY_CHAT" ]] || EXISTING_PRIMARY_CHAT="$(grep -m1 '^PRIMARY_CHAT_ID=' "$TELEGRAM_CONFIG_SOURCE" | cut -d= -f2- || true)"
    [[ -n "$EXISTING_ALLOWED_CHATS" ]] || EXISTING_ALLOWED_CHATS="$(grep -m1 '^ALLOWED_CHAT_IDS=' "$TELEGRAM_CONFIG_SOURCE" | cut -d= -f2- || true)"
  fi
  if [[ -z "$EXISTING_BOT_TOKEN" ]]; then
    echo "Non-interactive Telegram setup requires BOT_TOKEN." >&2
    echo "Export BOT_TOKEN or configure it in $ENV_TARGET and re-run." >&2
    exit 2
  fi
  if [[ ! "$EXISTING_BOT_TOKEN" =~ ^[0-9]{8,11}:[A-Za-z0-9_-]{35,}$ ]]; then
    echo "Telegram BOT_TOKEN is malformed; check the token issued by BotFather." >&2
    exit 2
  fi
  if [[ -n "$EXISTING_PRIMARY_CHAT" && ! "$EXISTING_PRIMARY_CHAT" =~ ^-?[0-9]+$ ]]; then
    echo "PRIMARY_CHAT_ID must be a numeric Telegram chat ID." >&2
    exit 2
  fi
  HAS_ALLOWED_CHAT=0
  IFS=',' read -r -a CHAT_ID_ARRAY <<< "$EXISTING_ALLOWED_CHATS"
  for CHAT_ID in "${CHAT_ID_ARRAY[@]}"; do
    CHAT_ID="${CHAT_ID//[[:space:]]/}"
    [[ -z "$CHAT_ID" ]] && continue
    HAS_ALLOWED_CHAT=1
    if [[ ! "$CHAT_ID" =~ ^-?[0-9]+$ ]]; then
      echo "ALLOWED_CHAT_IDS must contain only comma-separated numeric Telegram chat IDs." >&2
      exit 2
    fi
  done
  if [[ -z "$EXISTING_PRIMARY_CHAT" && "$HAS_ALLOWED_CHAT" == 0 ]]; then
    echo "Non-interactive Telegram setup requires PRIMARY_CHAT_ID or at least one ALLOWED_CHAT_IDS entry." >&2
    exit 2
  fi
fi

# Install host packages using the detected Linux package manager.
if command -v dnf >/dev/null 2>&1; then
  sudo dnf install -y python3.11 python3.11-devel gcc gcc-c++ make git curl libgomp mesa-libGL glib2
elif command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y python3.11 python3.11-dev python3.11-venv python3-pip git curl build-essential libopenblas-dev libgl1 libglib2.0-0
elif command -v zypper >/dev/null 2>&1; then
  sudo zypper --non-interactive install python311 python311-devel python311-pip gcc gcc-c++ make git curl libgomp1
else
  echo "Unsupported package manager. Install CPython 3.11 with venv/pip, Git, compiler tools and OpenCV runtime libraries manually." >&2
fi

if ! command -v "$PYTHON_BOOTSTRAP" >/dev/null 2>&1; then
  echo "CPython 3.11 is required, but '$PYTHON_BOOTSTRAP' was not found." >&2
  echo "Install Python 3.11 (Fedora: sudo dnf install python3.11; Debian: python3.11 python3.11-venv) and re-run." >&2
  exit 2
fi
BOOTSTRAP_MINOR="$("$PYTHON_BOOTSTRAP" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$BOOTSTRAP_MINOR" != "$PYTHON_MINOR" ]]; then
  echo "AWARESPAN requires CPython $PYTHON_MINOR; '$PYTHON_BOOTSTRAP' reports $BOOTSTRAP_MINOR." >&2
  exit 2
fi

# Rebuild an old venv instead of silently continuing with an incompatible ABI.
if [[ -x "$PYTHON" ]]; then
  EXISTING_MINOR="$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
  if [[ "$EXISTING_MINOR" != "$PYTHON_MINOR" ]]; then
    echo "Replacing existing Python ${EXISTING_MINOR:-unknown} environment with CPython $PYTHON_MINOR: $VENV"
    rm -rf -- "$VENV"
  fi
fi
"$PYTHON_BOOTSTRAP" -m venv "$VENV"
VENV_MINOR="$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$VENV_MINOR" != "$PYTHON_MINOR" ]]; then
  echo "Virtual environment creation selected Python $VENV_MINOR; expected $PYTHON_MINOR." >&2
  exit 2
fi

# Pin pip and install the CPU-only PyTorch pair first. The official CPU index
# contains CPython 3.11 wheels for Linux x86_64 and aarch64.
"$PYTHON" -m pip install --upgrade --only-binary=:all: \
  -c "$ROOT/requirements/constraints-py311.txt" \
  -r "$ROOT/requirements/bootstrap.txt"
"$PYTHON" -m pip install --only-binary=:all: \
  --index-url https://download.pytorch.org/whl/cpu \
  -c "$ROOT/requirements/constraints-py311.txt" \
  -r "$ROOT/requirements/torch-cpu.txt"
if [[ "$PROFILE" == pi ]]; then
  "$PYTHON" -m pip install --only-binary=:all: -r "$ROOT/requirements/runtime.txt"
elif [[ "$TRAIN" == yes ]]; then
  # Training workstations get runtime + development/test + dataset tooling.
  "$PYTHON" -m pip install --only-binary=:all: -r "$ROOT/requirements/dev.txt"
  "$PYTHON" -m pip install --only-binary=:all: -r "$ROOT/requirements/training.txt"
else
  "$PYTHON" -m pip install --only-binary=:all: -r "$ROOT/requirements/dev.txt"
fi
# Avoid installing opencv-python: SIP deliberately uses the headless build.
"$PYTHON" -m pip install --only-binary=:all: --no-deps -r "$ROOT/requirements/ultralytics.txt"

mkdir -p "$(dirname "$ENV_TARGET")"
if [[ "$(dirname "$ENV_TARGET")" != "$ROOT" ]]; then
  chmod 700 "$(dirname "$ENV_TARGET")"
fi

# Use the repository's single canonical .env. If this is an older installation,
# adopt its existing private config once; never create a second runtime config.
if [[ ! -f "$ENV_TARGET" && -n "$LEGACY_ENV_SOURCE" ]]; then
  cp -- "$LEGACY_ENV_SOURCE" "$ENV_TARGET"
  chmod 600 "$ENV_TARGET"
  echo "Migrated existing private settings from $LEGACY_ENV_SOURCE into $ENV_TARGET."
fi

if [[ -e "$ENV_TARGET" ]]; then
  chmod 600 "$ENV_TARGET"
  echo "Existing configuration preserved: $ENV_TARGET"
else
  if [[ ! -f "$ROOT/.env.example" ]]; then
    echo "Configuration template is missing: $ROOT/.env.example" >&2
    exit 2
  fi
  umask 077
  cp "$ROOT/.env.example" "$ENV_TARGET"
  chmod 600 "$ENV_TARGET"
  echo "Created private, sectioned configuration from .env.example: $ENV_TARGET"
fi

# Normalise existing or migrated config into the same logical sections as the
# tracked template. Current secrets and custom keys are preserved.
"$PYTHON" "$ROOT/scripts/merge_env.py" "$ENV_TARGET"

# If an existing env file was created, set non-secret selected values without
# overwriting any credentials or unrelated operator settings.
AWARESPAN_STATE_DIR="$STATE_DIR" python3 - "$ENV_TARGET" "$NODE_ID" "$BACKEND_URL" "$PRODUCTION" "$TRAIN" "$ROOT" <<'PY'
import os, pathlib, sys
path = pathlib.Path(sys.argv[1])
node_id, backend_url, production, train, root = sys.argv[2:]
root = pathlib.Path(root)
lines = path.read_text().splitlines() if path.exists() else []
updates = {
    "PI_NODE_ID": node_id,
    "MQTT_CLIENT_ID": node_id,
    "AWARESPAN_STATE_DIR": os.environ.get("AWARESPAN_STATE_DIR", "") or str(root / ".state"),
    "ML_TRAINING_ENABLED": "true" if train == "yes" else "false",
    "ML_DATASET_DIR": str(root / "datasets"),
    "ML_CHECKPOINT_DIR": str(root / "models" / "working" / "training_runs"),
    "ML_DEPLOYMENT_MANIFEST": "models/deployed/manifest.json",
}
if production == "yes":
    updates["BACKEND_API_URL"] = backend_url
seen = set()
out = []
for line in lines:
    if "=" in line and not line.lstrip().startswith("#"):
        key = line.split("=", 1)[0].strip()
        if key in updates:
            out.append(f"{key}={updates[key]}")
            seen.add(key)
            continue
    out.append(line)
for key, value in updates.items():
    if key not in seen:
        out.append(f"{key}={value}")
path.write_text("\n".join(out) + "\n")
os.chmod(path, 0o600)
PY

if [[ "$TELEGRAM_BOT" == yes ]]; then
  read_env_value() {
    local key="$1"
    if [[ -f "$ENV_TARGET" ]]; then
      grep -m1 "^${key}=" "$ENV_TARGET" | cut -d= -f2- || true
    fi
  }
  BOT_TOKEN_VALUE="${BOT_TOKEN:-$(read_env_value BOT_TOKEN)}"
  PRIMARY_CHAT_ID_VALUE="${PRIMARY_CHAT_ID:-$(read_env_value PRIMARY_CHAT_ID)}"
  ALLOWED_CHAT_IDS_VALUE="${ALLOWED_CHAT_IDS:-$(read_env_value ALLOWED_CHAT_IDS)}"
  if [[ -z "$BOT_TOKEN_VALUE" && "$NON_INTERACTIVE" == 0 ]]; then
    read -r -s -p "Telegram BOT_TOKEN from BotFather (input hidden): " BOT_TOKEN_VALUE
    echo
  fi
  if [[ -z "$PRIMARY_CHAT_ID_VALUE" && "$NON_INTERACTIVE" == 0 && -z "$ALLOWED_CHAT_IDS_VALUE" ]]; then
    read -r -p "Primary Telegram chat ID (numeric): " PRIMARY_CHAT_ID_VALUE
  fi
  BOT_TOKEN_VALUE="$BOT_TOKEN_VALUE" PRIMARY_CHAT_ID_VALUE="$PRIMARY_CHAT_ID_VALUE" \
    ALLOWED_CHAT_IDS_VALUE="$ALLOWED_CHAT_IDS_VALUE" ENV_TARGET="$ENV_TARGET" "$PYTHON" - <<'PYTELEGRAM'
import os, pathlib, re
path = pathlib.Path(os.environ["ENV_TARGET"])
token = os.environ.get("BOT_TOKEN_VALUE", "").strip()
primary = os.environ.get("PRIMARY_CHAT_ID_VALUE", "").strip()
allowed = os.environ.get("ALLOWED_CHAT_IDS_VALUE", "").strip()
if not re.fullmatch(r"[0-9]{8,11}:[A-Za-z0-9_-]{35,}", token):
    raise SystemExit("Invalid or missing Telegram BOT_TOKEN. Check the BotFather token and retry.")
chat_ids = [item.strip() for item in allowed.split(",") if item.strip()]
if primary and not re.fullmatch(r"-?[0-9]+", primary):
    raise SystemExit("PRIMARY_CHAT_ID must be a numeric Telegram chat ID.")
if any(not re.fullmatch(r"-?[0-9]+", item) for item in chat_ids):
    raise SystemExit("ALLOWED_CHAT_IDS must be comma-separated numeric Telegram chat IDs.")
if not primary and not chat_ids:
    raise SystemExit("Set PRIMARY_CHAT_ID or ALLOWED_CHAT_IDS; unrestricted bot access is disabled.")
updates = {"BOT_TOKEN": token, "PRIMARY_CHAT_ID": primary, "ALLOWED_CHAT_IDS": allowed}
lines = path.read_text().splitlines()
seen, out = set(), []
for line in lines:
    if "=" in line and not line.lstrip().startswith("#"):
        key = line.split("=", 1)[0].strip()
        if key in updates:
            out.append(f"{key}={updates[key]}")
            seen.add(key)
            continue
    out.append(line)
for key, value in updates.items():
    if key not in seen:
        out.append(f"{key}={value}")
path.write_text("\n".join(out) + "\n")
os.chmod(path, 0o600)
PYTELEGRAM
  unset BOT_TOKEN_VALUE PRIMARY_CHAT_ID_VALUE ALLOWED_CHAT_IDS_VALUE
  echo "Optional Telegram operator bot configured. Only explicitly authorised chat IDs can interact with it."
fi

if [[ "$PRODUCTION" == yes ]]; then
  API_KEY="${BACKEND_API_KEY:-}"
  if [[ -z "$API_KEY" && -f "$ENV_TARGET" ]]; then
    API_KEY="$(ENV_TARGET="$ENV_TARGET" "$PYTHON" - <<'PYKEY'
import os, pathlib
for line in pathlib.Path(os.environ["ENV_TARGET"]).read_text().splitlines():
    if line.startswith("BACKEND_API_KEY="):
        print(line.split("=", 1)[1])
        break
PYKEY
)"
  fi
  if [[ -z "$API_KEY" && "$NON_INTERACTIVE" == 0 ]]; then
    read -r -s -p "Paste backend DEVICE_API_KEY (input hidden): " API_KEY
    echo
  fi
  if [[ -z "$API_KEY" ]]; then
    echo "Production selected, but BACKEND_API_KEY is missing." >&2
    echo "Export BACKEND_API_KEY and re-run, or run interactively to enter it." >&2
    exit 2
  fi
  DEVICE_SECRET="${PI_DEVICE_SECRET:-}"
  if [[ -z "$DEVICE_SECRET" && -f "$ENV_TARGET" ]]; then
    DEVICE_SECRET="$(ENV_TARGET="$ENV_TARGET" "$PYTHON" - <<'PYSECRET'
import os, pathlib
for line in pathlib.Path(os.environ["ENV_TARGET"]).read_text().splitlines():
    if line.startswith("PI_DEVICE_SECRET="):
        print(line.split("=", 1)[1])
        break
PYSECRET
)"
  fi
  if [[ -z "$DEVICE_SECRET" && "$NON_INTERACTIVE" == 0 ]]; then
    read -r -s -p "Optional per-node PI_DEVICE_SECRET (Enter to skip): " DEVICE_SECRET
    echo
  fi
  # Write secrets without exposing them in process arguments or shell history.
  API_KEY="$API_KEY" DEVICE_SECRET="$DEVICE_SECRET" ENV_TARGET="$ENV_TARGET" "$PYTHON" - <<'PY'
import os, pathlib
p = pathlib.Path(os.environ["ENV_TARGET"])
lines = p.read_text().splitlines()
updates = {"BACKEND_API_KEY": os.environ["API_KEY"]}
if os.environ.get("DEVICE_SECRET"):
    updates["PI_DEVICE_SECRET"] = os.environ["DEVICE_SECRET"]
seen = set()
out = []
for line in lines:
    if "=" in line and not line.lstrip().startswith("#"):
        key = line.split("=", 1)[0].strip()
        if key in updates:
            out.append(f"{key}={updates[key]}")
            seen.add(key)
            continue
    out.append(line)
for key, value in updates.items():
    if key not in seen:
        out.append(f"{key}={value}")
p.write_text("\n".join(out) + "\n")
os.chmod(p, 0o600)
PY
  unset API_KEY DEVICE_SECRET
  echo "Production REST sync enabled for node $NODE_ID."
  echo "Use a distinct node ID for this Linux host; do not run it concurrently as sip-pi-001."
else
  echo "Production backend connection disabled."
fi

if [[ "$SERVICE" == yes ]]; then
  AWARESPAN_ENV_FILE="$ENV_TARGET" "$ROOT/scripts/install.sh"
fi
if [[ "$PROFILE" == pi && "$SERVICE" == yes ]]; then
  if [[ "$TELEGRAM_BOT" == yes ]]; then
    AWARESPAN_ENV_FILE="$ENV_TARGET" "$ROOT/scripts/install-telegram-bot.sh"
  else
    # The operator bot is an optional, separate service. Disabling it never
    # removes BOT_TOKEN because the same token may still power alert notices.
    "$ROOT/scripts/uninstall-telegram-bot.sh"
  fi
fi

echo
echo "Setup complete."
echo "  Profile       : $PROFILE"
echo "  Python        : CPython $PYTHON_MINOR"
echo "  Python env    : $VENV"
echo "  Private config: $ENV_TARGET"
echo "  ML training   : $TRAIN"
echo "  Production API: $PRODUCTION"
echo "  Telegram bot  : $TELEGRAM_BOT"
if [[ "$TELEGRAM_BOT" == yes ]]; then
  if [[ "$PROFILE" == pi && "$SERVICE" == yes ]]; then
    echo "  Telegram unit : awarespan-bot.service (enabled)"
  else
    echo "Run the optional bot manually:"
    echo "  AWARESPAN_ENV_FILE='$ENV_TARGET' '$ROOT/pi/telegram_bot/run.sh'"
  fi
fi
if [[ "$PROFILE" == linux ]]; then
  echo
  echo "Run locally:"
  echo "  AWARESPAN_ENV_FILE='$ENV_TARGET' '$PYTHON' -m node_runtime.main"
  echo "Stream this machine's webcam in another terminal:"
  echo "  '$PYTHON' laptop/stream_client.py --pi-host 127.0.0.1 --pi-port 8766 --camera 0 --fps 8"
fi
if [[ "$TRAIN" == yes ]]; then
  echo "Training dependencies are installed. Review ml_pipeline/training/README.md and dataset/job manifests before training."
fi
