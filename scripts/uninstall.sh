#!/usr/bin/env bash
# ─── AWARESPAN Production Node Uninstaller ───────────────────────────────────
# Project: AWARESPAN
# Tagline: Awareness Without Boundaries.
# Official problem statement: An AI-Powered Safety Device.
# Contact: awarespan@bchbenjamin.in
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

PURGE=false
if [[ "${1:-}" == "--purge" ]]; then
    PURGE=true
fi

echo "============================================================"
echo " AWARESPAN Edge Node Uninstallation System"
echo " Awareness Without Boundaries."
echo "============================================================"

SERVICES=(
    "awarespan-node.service"
    "awarespan-power-monitor.service"
    "awarespan-updater.service"
    "awarespan-updater.timer"
    "awarespan-training.service"
)

if command -v systemctl >/dev/null 2>&1 && [[ -d "/run/systemd/system" ]]; then
    echo "Stopping and disabling AWARESPAN services..."
    for s in "${SERVICES[@]}"; do
        if systemctl list-unit-files "${s}" >/dev/null 2>&1; then
            echo "Stopping ${s}..."
            sudo systemctl stop "${s}" 2>/dev/null || true
            sudo systemctl disable "${s}" 2>/dev/null || true
        fi
        if [[ -f "/etc/systemd/system/${s}" ]]; then
            echo "Removing /etc/systemd/system/${s}..."
            sudo rm -f "/etc/systemd/system/${s}"
        fi
    done

    if [[ -f "/etc/sudoers.d/awarespan" ]]; then
        echo "Removing /etc/sudoers.d/awarespan..."
        sudo rm -f "/etc/sudoers.d/awarespan"
    fi

    echo "Reloading systemd daemon..."
    sudo systemctl daemon-reload
fi

if [[ "${PURGE}" == "true" ]]; then
    echo "Purging persistent AWARESPAN data (/var/lib/awarespan, /var/log/awarespan)..."
    sudo rm -rf /var/lib/awarespan /var/log/awarespan /var/lock/awarespan
fi

echo "Uninstallation complete."
