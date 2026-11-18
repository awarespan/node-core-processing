#!/usr/bin/env bash
# Start the temporary interactive Telegram bot. It is deliberately opt-in.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${AWARESPAN_PYTHON:-${ROOT}/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then PYTHON="$(command -v python3)"; fi
cd "$ROOT"
exec "$PYTHON" -m pi.telegram_bot.bot "$@"
