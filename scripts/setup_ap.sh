#!/usr/bin/env bash
# ==============================================================================
# AWARESPAN — Wi-Fi Access Point Configuration Utility
# LAN-First Autonomous Access Point for Browser Volunteered Media
#
# Project: AWARESPAN
# Tagline: Awareness Without Boundaries.
# Official problem statement: An AI-Powered Safety Device.
# Contact: awarespan@bchbenjamin.in
# ==============================================================================

set -euo pipefail

AP_CON_NAME="AWARESPAN-AP"
DEFAULT_SSID="AWARESPAN-AP"
DEFAULT_PASS="awarespan123"
AP_GATEWAY_IP="192.168.4.1"
AP_CIDR="24"
WIFI_IFACE="wlan0"

# Colors
C_RESET="\033[0m"
C_BOLD="\033[1m"
C_GREEN="\033[32m"
C_YELLOW="\033[33m"
C_RED="\033[31m"
C_CYAN="\033[36m"

print_header() {
    echo -e "${C_CYAN}${C_BOLD}"
    echo "================================================================="
    echo "  AWARESPAN — Wi-Fi Access Point Management"
    echo "  LAN-First Offline Volunteer Media Ingestion"
    echo "=================================================================${C_RESET}"
}

check_nmcli() {
    if ! command -v nmcli &>/dev/null; then
        echo -e "${C_RED}[!] Error: nmcli (NetworkManager) is not installed.${C_RESET}"
        exit 1
    fi
}

ap_status() {
    check_nmcli
    echo -e "${C_BOLD}Active Network Interfaces:${C_RESET}"
    ip -brief addr show || true
    echo ""

    echo -e "${C_BOLD}NetworkManager Connections:${C_RESET}"
    nmcli -p con show || true
    echo ""

    if nmcli con show --active | grep -q "${AP_CON_NAME}"; then
        echo -e "${C_GREEN}[*] Status: ${AP_CON_NAME} is ACTIVE on ${WIFI_IFACE}.${C_RESET}"
        echo -e "    Access Point IP: ${C_BOLD}${AP_GATEWAY_IP}${C_RESET}"
        echo -e "    Volunteer Gateway Portal: ${C_BOLD}https://${AP_GATEWAY_IP}:8443/${C_RESET}"
    else
        echo -e "${C_YELLOW}[*] Status: ${AP_CON_NAME} is INACTIVE.${C_RESET}"
    fi
}

enable_ap() {
    check_nmcli
    SSID="${1:-$DEFAULT_SSID}"
    PASS="${2:-$DEFAULT_PASS}"

    echo -e "${C_CYAN}[*] Configuring AP connection '${AP_CON_NAME}' on interface ${WIFI_IFACE}...${C_RESET}"
    echo -e "    SSID: ${SSID}"
    echo -e "    Gateway: ${AP_GATEWAY_IP}/${AP_CIDR}"

    # Remove existing connection if present
    if nmcli con show "${AP_CON_NAME}" &>/dev/null; then
        echo -e "${C_YELLOW}[*] Removing existing '${AP_CON_NAME}' profile...${C_RESET}"
        nmcli con delete "${AP_CON_NAME}" || true
    fi

    # Create hotspot connection
    nmcli con add type wifi ifname "${WIFI_IFACE}" con-name "${AP_CON_NAME}" autoconnect yes ssid "${SSID}"
    nmcli con modify "${AP_CON_NAME}" 802-11-wireless.mode ap 802-11-wireless.band bg
    nmcli con modify "${AP_CON_NAME}" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "${PASS}"
    nmcli con modify "${AP_CON_NAME}" ipv4.method shared ipv4.addresses "${AP_GATEWAY_IP}/${AP_CIDR}"
    nmcli con modify "${AP_CON_NAME}" ipv6.method ignore

    echo -e "${C_CYAN}[*] Activating ${AP_CON_NAME}...${C_RESET}"
    nmcli con up "${AP_CON_NAME}"

    echo -e "${C_GREEN}[✓] Access Point '${SSID}' successfully activated!${C_RESET}"
    echo -e "    Volunteer Devices can connect to Wi-Fi '${SSID}' and navigate to:"
    echo -e "    ${C_BOLD}https://${AP_GATEWAY_IP}:8443/${C_RESET}"
}

disable_ap() {
    check_nmcli
    echo -e "${C_CYAN}[*] Deactivating ${AP_CON_NAME}...${C_RESET}"
    nmcli con down "${AP_CON_NAME}" || true
    echo -e "${C_GREEN}[✓] Access Point deactivated.${C_RESET}"
}

rollback_ap() {
    check_nmcli
    echo -e "${C_YELLOW}[*] Rolling back and deleting ${AP_CON_NAME} connection profile...${C_RESET}"
    nmcli con down "${AP_CON_NAME}" || true
    nmcli con delete "${AP_CON_NAME}" || true
    echo -e "${C_GREEN}[✓] Rollback complete.${C_RESET}"
}

usage() {
    echo "Usage: $0 {--status|--enable [SSID] [PASS]|--disable|--rollback}"
    echo "  --status               Show AP and network state"
    echo "  --enable [SSID] [PASS] Enable Wi-Fi Hotspot (defaults: AWARESPAN-AP / awarespan123)"
    echo "  --disable              Deactivate Wi-Fi Hotspot"
    echo "  --rollback             Delete AP configuration profile"
    exit 1
}

main() {
    print_header
    ACTION="${1:-status}"

    case "$ACTION" in
        --status|status)
            ap_status
            ;;
        --enable|enable)
            enable_ap "${2:-$DEFAULT_SSID}" "${3:-$DEFAULT_PASS}"
            ;;
        --disable|disable)
            disable_ap
            ;;
        --rollback|rollback)
            rollback_ap
            ;;
        *)
            usage
            ;;
    esac
}

main "$@"
