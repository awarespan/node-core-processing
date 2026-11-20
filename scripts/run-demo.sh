#!/usr/bin/env bash
# Run the AWARESPAN node + volunteer portal on any Linux host (laptop, Codespace, Pi).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
  echo "Missing ${PYTHON}. Run ./scripts/setup.sh first." >&2
  exit 2
fi
if [[ ! -f "${ROOT}/static/volunteer/index.html" ]]; then
  echo "Volunteer portal build is missing. Build web/volunteer-portal and sync dist/ to static/volunteer/." >&2
  exit 2
fi
export AWARESPAN_ENV_FILE="${AWARESPAN_ENV_FILE:-${ROOT}/.env}"
# The portal build always lives beside this checkout; ignore stale absolute paths
# left behind by copying a .env from another Linux device.
export VOLUNTEER_PORTAL_STATIC_DIR="${ROOT}/static/volunteer"
if [[ ! -f "${AWARESPAN_ENV_FILE}" ]]; then
  echo "Missing ${AWARESPAN_ENV_FILE}. Run ./scripts/setup.sh first." >&2
  exit 2
fi
# Read non-secret settings without sourcing the .env (values may contain shell metacharacters).
read_env() { sed -n "s/^$1=//p" "${AWARESPAN_ENV_FILE}" | tail -n 1 | tr -d '\r'; }
RUNTIME_PORT="$(read_env RUNTIME_PORT)"; RUNTIME_PORT="${RUNTIME_PORT:-8766}"
GATEWAY_PORT="$(read_env VOLUNTEER_GATEWAY_PORT)"; GATEWAY_PORT="${GATEWAY_PORT:-8443}"
TLS="$(read_env VOLUNTEER_GATEWAY_TLS)"; TLS="${TLS:-false}"
# Keep the launcher usable by an ordinary Linux user. Preserve the configured
# system state path when writable; otherwise fall back to repo-local state.
STATE_DIR="$(read_env AWARESPAN_STATE_DIR)"; STATE_DIR="${STATE_DIR:-/var/lib/awarespan}"
if ! mkdir -p "${STATE_DIR}" 2>/dev/null || [[ ! -w "${STATE_DIR}" ]]; then
  STATE_DIR="${ROOT}/state/runtime"
  mkdir -p "${STATE_DIR}"
  chmod 700 "${STATE_DIR}"
  export AWARESPAN_STATE_DIR="${STATE_DIR}"
  TOTP_FILE="$(read_env TOTP_SECRET_FILE)"
  if [[ -z "${TOTP_FILE}" || "${TOTP_FILE}" == "/var/lib/awarespan/totp_secret.json" ]]; then
    export TOTP_SECRET_FILE="${STATE_DIR}/totp_secret.json"
  fi
  echo "  State path:   ${STATE_DIR} (configured system path is not writable)"
fi
if [[ "${TLS,,}" == "true" ]]; then
  SCHEME="https"; WS_SCHEME="wss"
  if [[ ! -s "${ROOT}/state/certs/volunteer_gateway.crt" || ! -s "${ROOT}/state/certs/volunteer_gateway.key" ]]; then
    echo "TLS is enabled but the LAN certificate is missing. Run ./scripts/setup-lan-https.sh <LAN-IP>, or disable VOLUNTEER_GATEWAY_TLS for local-only testing." >&2
    exit 2
  fi
else
  SCHEME="http"; WS_SCHEME="ws"
fi
mapfile -t LAN_IPS < <(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | grep -v '^127\.' | sort -u || true)
echo "AWARESPAN Linux node starting on ${HOSTNAME:-this device}"
echo "  Local portal: ${SCHEME}://127.0.0.1:${GATEWAY_PORT}/"
for ip in "${LAN_IPS[@]}"; do echo "  LAN portal:   ${SCHEME}://${ip}:${GATEWAY_PORT}/"; done
if command -v avahi-publish-address >/dev/null 2>&1 && pgrep -x avahi-daemon >/dev/null 2>&1; then
  avahi-publish-address -R awarespan.local "${LAN_IPS[0]:-127.0.0.1}" >/dev/null 2>&1 &
  MDNS_PID=$!
  echo "  mDNS portal:  ${SCHEME}://awarespan.local:${GATEWAY_PORT}/"
else
  MDNS_PID=""
  echo "  mDNS:         unavailable (install/start Avahi to use awarespan.local)"
fi
echo "  Runtime WS:   ${WS_SCHEME}://<same-host>:${RUNTIME_PORT}/"
echo "Press Ctrl-C to stop. Run only one node on this LAN at a time."
cleanup() { if [[ -n "${MDNS_PID}" ]]; then kill "${MDNS_PID}" 2>/dev/null || true; fi; }
trap cleanup EXIT INT TERM
cd "${ROOT}"
"${PYTHON}" -m node_runtime.main --host 0.0.0.0 --port "${RUNTIME_PORT}" --volunteer-host 0.0.0.0 --volunteer-port "${GATEWAY_PORT}" &
NODE_PID=$!
wait "${NODE_PID}"
