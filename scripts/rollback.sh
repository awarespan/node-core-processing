#!/usr/bin/env bash
# ─── AWARESPAN Manual Rollback Trigger ───────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -f "${REPO_ROOT}/.venv/bin/python3" ]]; then
    PYTHON="${REPO_ROOT}/.venv/bin/python3"
elif [[ -f "${HOME}/edge-ai/pi/.venv/bin/python3" ]]; then
    PYTHON="${HOME}/edge-ai/pi/.venv/bin/python3"
else
    PYTHON="python3"
fi

export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"
cd "${REPO_ROOT}"
exec "${PYTHON}" -m node_manager.cli rollback "$@"
