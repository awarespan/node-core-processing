#!/usr/bin/env bash
# Start the temporary interactive Telegram bot. It is deliberately opt-in.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${AWARESPAN_PYTHON:-${ROOT}/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
  echo "AWARESPAN virtualenv not found: $PYTHON" >&2
  echo "Run ./scripts/setup.sh first." >&2
  exit 2
fi
if [[ -z "${AWARESPAN_ENV_FILE:-}" ]]; then
  export AWARESPAN_ENV_FILE="$ROOT/.env"
fi
if [[ ! -f "$AWARESPAN_ENV_FILE" ]]; then
  echo "AWARESPAN configuration not found: $AWARESPAN_ENV_FILE" >&2
  echo "Run ./scripts/setup.sh to create the shared root .env file." >&2
  exit 2
fi
cd "$ROOT"
exec "$PYTHON" -m pi.telegram_bot.bot "$@"
