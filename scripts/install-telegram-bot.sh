#!/usr/bin/env bash
# Install the optional AWARESPAN Telegram operator bot as a separate systemd unit.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$ROOT/.venv/bin/python"
CURRENT_USER="${SUDO_USER:-$(id -un)}"
ENV_SOURCE="${AWARESPAN_ENV_FILE:-$ROOT/.env}"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "AWARESPAN Python environment is missing: $VENV_PYTHON" >&2
  exit 2
fi
if [[ ! -f "$ENV_SOURCE" ]]; then
  echo "Private AWARESPAN config not found: $ENV_SOURCE" >&2
  exit 2
fi

# Validate secrets and an allowlist without ever printing the values.
ENV_SOURCE="$ENV_SOURCE" "$VENV_PYTHON" - <<'PY'
import os
import re
from pathlib import Path
from dotenv import dotenv_values
values = dotenv_values(Path(os.environ["ENV_SOURCE"]))
token = str(values.get("BOT_TOKEN") or "").strip()
primary = str(values.get("PRIMARY_CHAT_ID") or "").strip()
allowed = [x.strip() for x in str(values.get("ALLOWED_CHAT_IDS") or "").split(",") if x.strip()]
if not re.fullmatch(r"[0-9]{8,11}:[A-Za-z0-9_-]{35,}", token):
    raise SystemExit("BOT_TOKEN is missing or malformed in the private config.")
if primary and not re.fullmatch(r"-?[0-9]+", primary):
    raise SystemExit("PRIMARY_CHAT_ID must be a numeric Telegram chat ID.")
if any(not re.fullmatch(r"-?[0-9]+", chat_id) for chat_id in allowed):
    raise SystemExit("ALLOWED_CHAT_IDS must contain only comma-separated numeric chat IDs.")
if not (primary or allowed):
    raise SystemExit("Set PRIMARY_CHAT_ID or ALLOWED_CHAT_IDS; the bot refuses unrestricted access.")
PY

command -v systemctl >/dev/null 2>&1 || { echo "systemctl is not available on this host." >&2; exit 2; }
chmod 600 "$ENV_SOURCE"

TMP_UNIT="$(mktemp)"
trap 'rm -f "$TMP_UNIT"' EXIT
ENV_SOURCE_ESCAPED="$(printf '%s' "$ENV_SOURCE" | sed 's/[\\&|]/\\&/g')"
sed \
  -e "s|%USER%|$CURRENT_USER|g" \
  -e "s|%WORKDIR%|$ROOT|g" \
  -e "s|%PYTHON%|$VENV_PYTHON|g" \
  -e "s|%ENV_FILE%|$ENV_SOURCE_ESCAPED|g" \
  pi/telegram_bot/awarespan-bot.service > "$TMP_UNIT"
sudo install -o root -g root -m 644 "$TMP_UNIT" /etc/systemd/system/awarespan-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now awarespan-bot.service

echo "Optional Telegram bot installed and started as awarespan-bot.service."
echo "Logs: sudo journalctl -u awarespan-bot.service -f"
