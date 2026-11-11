#!/usr/bin/env bash
# ─── AWARESPAN Production Node Installer ─────────────────────────────────────
# Project: AWARESPAN
# Tagline: Awareness Without Boundaries.
# Official problem statement: An AI-Powered Safety Device.
# Contact: awarespan@bchbenjamin.in
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CURRENT_USER="${SUDO_USER:-$(whoami)}"
CURRENT_HOME=$(getent passwd "${CURRENT_USER}" | cut -d: -f6)

echo "============================================================"
echo " AWARESPAN Edge Node Installation System"
echo " Awareness Without Boundaries."
echo "============================================================"
echo "Target User:     ${CURRENT_USER}"
echo "User Home:       ${CURRENT_HOME}"
echo "Repository Root: ${REPO_ROOT}"

# 1. Check OS and Architecture
OS_NAME=$(uname -s)
ARCH=$(uname -m)
echo "Platform:        ${OS_NAME} ${ARCH}"

if [[ "${OS_NAME}" != "Linux" ]]; then
    echo "WARNING: AWARESPAN production nodes are designed for Linux (Debian / Raspberry Pi OS)."
fi

# 2. System Packages (Debian/Ubuntu/Raspberry Pi OS)
if command -v apt-get >/dev/null 2>&1; then
    echo "Checking system package prerequisites..."
    sudo apt-get update -qq || true
    sudo apt-get install -y -qq python3-venv python3-pip git curl libopenblas-dev libgl1 libglib2.0-0 >/dev/null || true
fi

# 3. Setup Persistent Directories
echo "Setting up persistent system directories..."
sudo mkdir -p /var/lib/awarespan /var/log/awarespan /var/lock/awarespan
sudo chown -R "${CURRENT_USER}:${CURRENT_USER}" /var/lib/awarespan /var/log/awarespan /var/lock/awarespan
mkdir -p "${REPO_ROOT}/state" "${REPO_ROOT}/logs" "${REPO_ROOT}/shared/models"

# 4. Setup Python Virtual Environment
VENV_PATH="${REPO_ROOT}/.venv"
if [[ -f "${CURRENT_HOME}/edge-ai/pi/.venv/bin/python3" ]]; then
    echo "Found existing edge-ai virtual environment at ${CURRENT_HOME}/edge-ai/pi/.venv"
    PYTHON_EXEC="${CURRENT_HOME}/edge-ai/pi/.venv/bin/python3"
elif [[ -f "${VENV_PATH}/bin/python3" ]]; then
    echo "Using existing repository virtual environment at ${VENV_PATH}"
    PYTHON_EXEC="${VENV_PATH}/bin/python3"
else
    echo "Creating Python virtual environment at ${VENV_PATH}..."
    python3 -m venv "${VENV_PATH}"
    PYTHON_EXEC="${VENV_PATH}/bin/python3"
fi

# 5. Install Runtime Requirements
echo "Installing runtime dependencies..."
"${PYTHON_EXEC}" -m pip install --upgrade pip --no-warn-script-location >/dev/null
"${PYTHON_EXEC}" -m pip install --no-warn-script-location -r "${REPO_ROOT}/requirements/runtime.txt"

# 6. Setup Configuration Environment (stored OUTSIDE git repository)
CONFIG_DIR="/etc/awarespan"
sudo mkdir -p "${CONFIG_DIR}"
sudo chown "${CURRENT_USER}:${CURRENT_USER}" "${CONFIG_DIR}"
ENV_TARGET="${CONFIG_DIR}/node.env"

if [[ ! -f "${ENV_TARGET}" ]]; then
    if [[ -f "${CURRENT_HOME}/edge-ai/.env" ]]; then
        echo "Installing environment configuration to ${ENV_TARGET}..."
        cp "${CURRENT_HOME}/edge-ai/.env" "${ENV_TARGET}"
        chmod 600 "${ENV_TARGET}"
    elif [[ -f "${REPO_ROOT}/.env.example" ]]; then
        echo "Creating initial template configuration at ${ENV_TARGET}..."
        cp "${REPO_ROOT}/.env.example" "${ENV_TARGET}"
        chmod 600 "${ENV_TARGET}"
    fi
fi

# 7. Configure and Deploy Systemd Services
if command -v systemctl >/dev/null 2>&1 && [[ -d "/run/systemd/system" ]]; then
    echo "Configuring systemd service definitions..."
    SYSTEMD_DIR="${REPO_ROOT}/deployment/systemd"

    # Temporary rendering directory
    TMP_SYSTEMD=$(mktemp -d)
    for service_file in "${SYSTEMD_DIR}"/*.service "${SYSTEMD_DIR}"/*.timer; do
        if [[ -f "${service_file}" ]]; then
            base_name=$(basename "${service_file}")
            sed \
                -e "s|%USER%|${CURRENT_USER}|g" \
                -e "s|%WORKDIR%|${REPO_ROOT}|g" \
                -e "s|%PYTHON%|${PYTHON_EXEC}|g" \
                "${service_file}" > "${TMP_SYSTEMD}/${base_name}"
            
            echo "Installing ${base_name} to /etc/systemd/system/..."
            sudo cp "${TMP_SYSTEMD}/${base_name}" "/etc/systemd/system/${base_name}"
        fi
    done
    rm -rf "${TMP_SYSTEMD}"

    # Sudoers configuration for unprivileged service restarts by auto-updater
    echo "Installing updater sudoers policy..."
    sudo mkdir -p /etc/sudoers.d
    sudo bash -c "echo '${CURRENT_USER} ALL=(ALL) NOPASSWD: /bin/systemctl restart awarespan-node.service, /bin/systemctl restart awarespan-power-monitor.service, /bin/systemctl restart awarespan-bot.service, /bin/systemctl restart awarespan-updater.service, /bin/systemctl daemon-reload' > /etc/sudoers.d/awarespan"
    sudo chmod 0440 /etc/sudoers.d/awarespan

    echo "Reloading systemd daemon..."
    sudo systemctl daemon-reload

    echo "Enabling and starting AWARESPAN services..."
    sudo systemctl enable --now awarespan-updater.timer
    sudo systemctl enable --now awarespan-power-monitor.service
    sudo systemctl enable --now awarespan-node.service
    sudo systemctl enable --now awarespan-bot.service || true

    # awarespan-training.service remains disabled by default on production nodes
    echo "ML training service remains unlinked and disabled by default on production node."
fi

# 8. Set execute permissions on scripts
chmod +x "${REPO_ROOT}/scripts"/*.sh

echo "============================================================"
echo " Installation completed successfully!"
echo "============================================================"
"${REPO_ROOT}/scripts/status.sh" || true
