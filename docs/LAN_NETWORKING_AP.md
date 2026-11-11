# AWARESPAN — LAN-First Networking & Autonomous Wi-Fi AP Guide

**Project:** AWARESPAN  
**Tagline:** Awareness Without Boundaries.  
**Problem Statement:** An AI-Powered Safety Device.  
**Contact:** awarespan@bchbenjamin.in  
**Target:** Raspberry Pi 5 (4 GB RAM), Bookworm / Debian 12  

---

## 1. Network Topology Overview

AWARESPAN is engineered to operate in environments where cloud infrastructure, wide-area networks, and public DNS are completely unavailable. During field evaluations, the Raspberry Pi 5 can act as its own standalone Wi-Fi Access Point (Hotspot) or connect to an existing local subnet.

```
+-------------------------------------------------------------+
|                      EVALUATION SUBNET                      |
|                                                             |
|   +-----------------------+         +-------------------+   |
|   |  Volunteer Device 01  |         |  Android Client   |   |
|   |  (Phone Camera & Mic) |         |  (App & Alert UI) |   |
|   +-----------+-----------+         +---------+---------+   |
|               |                               |             |
|   WLAN:       |  WSS / HTTPS                  | MQTT / HTTP |
|   192.168.4.x |  (Port 8443)                  | (Port 8765) |
|               |                               |             |
|               +---------------+---------------+             |
|                               |                             |
|              +----------------v----------------+            |
|              |         Raspberry Pi 5          |            |
|              |   Hotspot IP: 192.168.4.1       |            |
|              |   Eth0: 192.168.0.125 (SSH)     |            |
|              +---------------------------------+            |
|                                                             |
+-------------------------------------------------------------+
```

---

## 2. Autonomous Wi-Fi AP Management (`scripts/setup_ap.sh`)

Network management on Raspberry Pi OS Bookworm utilizes NetworkManager (`nmcli`). The included automation script configures and controls the local Wi-Fi hotspot safely without disrupting wired Ethernet (`eth0`).

### 2.1 Access Point Parameters
- **Connection Profile:** `AWARESPAN-AP`
- **Default SSID:** `AWARESPAN-AP` (or configured via `AP_SSID`)
- **Default WPA2 Password:** `awarespan123` (or configured via `AP_PASSWORD`)
- **Interface:** `wlan0`
- **Subnet / Gateway:** `192.168.4.1/24`
- **DHCP Pool:** `192.168.4.10` – `192.168.4.50` (managed by NetworkManager internal dnsmasq)

### 2.2 CLI Usage Commands

```bash
# Check current AP and interface status
./scripts/setup_ap.sh --status

# Activate the Wi-Fi Hotspot with custom SSID and password
sudo ./scripts/setup_ap.sh --enable "AWARESPAN-AP" "awarespan123"

# Deactivate the Wi-Fi Hotspot (returns wlan0 to standby)
sudo ./scripts/setup_ap.sh --disable

# Completely rollback and delete the AP connection profile
sudo ./scripts/setup_ap.sh --rollback
```

> [!IMPORTANT]
> The setup script exclusively targets `wlan0`. The wired Ethernet connection (`eth0`) is never altered or disconnected, ensuring active SSH debugging sessions remain live throughout the evaluation.

---

## 3. Browser Secure Context & HTTPS Acceptance

Web browsers enforce the W3C Secure Context specification: APIs such as `navigator.mediaDevices.getUserMedia` are blocked on plain HTTP origins unless the hostname is `localhost` or `127.0.0.1`.

Since volunteer devices connect via LAN IP (e.g., `https://192.168.4.1:8443` or `https://192.168.0.125:8443`), AWARESPAN serves the portal over HTTPS using a node-generated self-signed certificate.

### Step-by-Step Browser Acceptance:
1. **Connect to Wi-Fi:** On the phone or laptop, join the `AWARESPAN-AP` Wi-Fi network (password: `awarespan123`).
2. **Open Browser:** Navigate to `https://192.168.4.1:8443`.
3. **Bypass Self-Signed Certificate Warning:**
   - **Google Chrome / Chromium:** Tap **Advanced** $\rightarrow$ Tap **Proceed to 192.168.4.1 (unsafe)**.
   - **Apple iOS Safari:** Tap **Show Details** $\rightarrow$ Tap **visit this website** $\rightarrow$ Tap **Visit Website** to confirm.
   - **Mozilla Firefox:** Tap **Advanced** $\rightarrow$ Tap **Accept the Risk and Continue**.
4. Once accepted, browser camera and microphone permissions can be granted without restriction.

---

## 4. Multi-Interface Redundancy

AWARESPAN seamlessly binds its services to all network interfaces (`0.0.0.0`):
- **Wired LAN:** Accessible via `192.168.0.125` for development, monitoring, and debugging.
- **Autonomous Wi-Fi AP:** Accessible via `192.168.4.1` for evaluation volunteers and Android test devices.
- **Loopback:** `127.0.0.1` for local integration tests and synthetic stream injection.
