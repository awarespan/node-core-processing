#!/usr/bin/env bash
# ==============================================================================
# AWARESPAN — Deploy Volunteer Gateway Frontend
# Deploys compiled volunteer frontend build artifacts to static hosting directory.
#
# Project: AWARESPAN
# Tagline: Awareness Without Boundaries.
# Official problem statement: An AI-Powered Safety Device.
# Contact: awarespan@bchbenjamin.in
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_DIR="${REPO_ROOT}/static/volunteer"
SYSTEM_TARGET="/var/www/awarespan/volunteer"

SOURCE_PATH="${1:-}"

echo "======================================================="
echo "  AWARESPAN — VOLUNTEER FRONTEND DEPLOYMENT"
echo "======================================================="

mkdir -p "${TARGET_DIR}"

if [ -z "${SOURCE_PATH}" ]; then
    echo "[i] No source build path provided."
    echo "[i] Static volunteer portal directory is ready at: ${TARGET_DIR}"
    echo "Usage: $0 <path-to-dist-or-zip>"
    exit 0
fi

if [ -f "${SOURCE_PATH}" ]; then
    if [[ "${SOURCE_PATH}" == *.zip ]]; then
        echo "[*] Extracting zip archive: ${SOURCE_PATH} -> ${TARGET_DIR}..."
        unzip -q -o "${SOURCE_PATH}" -d "${TARGET_DIR}"
    elif [[ "${SOURCE_PATH}" == *.tar.gz || "${SOURCE_PATH}" == *.tgz ]]; then
        echo "[*] Extracting tar archive: ${SOURCE_PATH} -> ${TARGET_DIR}..."
        tar -xzf "${SOURCE_PATH}" -C "${TARGET_DIR}"
    else
        echo "[!] Unsupported archive format: ${SOURCE_PATH}"
        exit 1
    fi
elif [ -d "${SOURCE_PATH}" ]; then
    echo "[*] Syncing build directory: ${SOURCE_PATH} -> ${TARGET_DIR}..."
    rsync -av --delete "${SOURCE_PATH}/" "${TARGET_DIR}/"
else
    echo "[!] Source path not found: ${SOURCE_PATH}"
    exit 1
fi

chmod -R 755 "${TARGET_DIR}"

# Optional sync to system directory if writable
if [ -d "/var/www/awarespan" ] && [ -w "/var/www/awarespan" ]; then
    mkdir -p "${SYSTEM_TARGET}"
    rsync -a --delete "${TARGET_DIR}/" "${SYSTEM_TARGET}/"
    echo "[✓] Also synced to system target: ${SYSTEM_TARGET}"
fi

echo "======================================================="
echo "✓ Volunteer frontend deployed successfully!"
echo "Target directory: ${TARGET_DIR}"
echo "======================================================="
