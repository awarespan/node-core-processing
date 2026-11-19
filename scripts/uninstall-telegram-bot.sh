#!/usr/bin/env bash
# Remove only the optional AWARESPAN Telegram operator bot service.
set -Eeuo pipefail
UNIT=awarespan-bot.service
if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl disable --now "$UNIT" 2>/dev/null || true
  sudo rm -f "/etc/systemd/system/$UNIT"
  sudo systemctl daemon-reload
fi
echo "Optional Telegram bot service removed. The shared root .env and its credentials were left untouched."
