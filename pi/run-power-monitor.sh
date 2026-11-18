#!/usr/bin/env bash
# Start the Raspberry Pi power/thermal monitor.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${AWARESPAN_PYTHON:-${ROOT}/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then PYTHON="$(command -v python3)"; fi
cd "$ROOT"
exec "$PYTHON" -m node_runtime.monitoring.power_monitor "$@"
