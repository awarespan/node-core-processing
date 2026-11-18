 Diagnostic & Resolution Report: Raspberry Pi 5 USB-C Ethernet Gadget on Windows

  The USB-C networking connection between your Windows laptop and Raspberry Pi 5 has been diagnosed, re-architected,
  and verified end-to-end.
  ──────
  ## 1. Root Cause Analysis

  ### A. Why Windows bound USB Serial Device (COM3)

  1. Legacy g_ether Descriptors:
  The initial setup loaded the legacy Linux g_ether kernel module. By default, g_ether presents CDC-ACM style RNDIS
  identifiers:
      • USB Device Class 0x02 (Communications), SubClass 0x02 (Abstract Control Model / ACM), Protocol 0xFF.
  2. Windows 11 Driver Matching:
  In Windows 11 (build 26100 / 24H2), Microsoft's inbox usbser.inf driver has a prioritized compatible-ID match for
  USB\Class_02&SubClass_02. Consequently, Windows automatically bound usbser.sys to the device, enumerating it as a
  serial COM port (COM3).
  3. Hidden / Deprecated RNDIS:
  Microsoft deprecated legacy RNDIS in Windows 11 and added ExcludeFromSelect=* to C:\Windows\INF\rndiscmp.inf. This
  explicitly suppressed "Remote NDIS Compatible Device" from appearing in Device Manager's driver-selection UI.
  4. Link Failure:
  Because Windows bound a serial driver instead of a network driver, the USB Ethernet protocol was never initialized
  by the host. As a result, the Pi's usb0 interface remained in a NO-CARRIER / DOWN state.
  ──────
  ## 2. Solution: Modern CDC-NCM with Microsoft OS Descriptors

  Modern Windows 10 (1903+) and Windows 11 natively support CDC-NCM (Network Control Model) via
  C:\Windows\INF\usbncm.inf (UsbNcm.sys), which:

  • Operates out-of-the-box with zero third-party or unsigned drivers.
  • Provides significantly higher throughput and lower latency than legacy RNDIS.
  • Automatically enumerates as a high-speed network adapter (UsbNcm Host Device).

  ### Changes Implemented on the Raspberry Pi 5

  1. Replaced g_ether with ConfigFS Gadget (libcomposite + usb_f_ncm):
      • Created /usr/local/bin/pi-usb-gadget-start.sh and /usr/local/bin/pi-usb-gadget-stop.sh.
      • Configured USB IDs: Vendor 0x1d6b, Product 0x0104, Device Class 0xef (Composite IAD).
      • Configured deterministic locally administered MAC addresses:
          • Host (Windows): 02:00:00:00:00:01
          • Device (Pi): 02:00:00:00:00:02
      • Configured Microsoft OS 1.0 Descriptors (MSFT100 / WINNCM), allowing Windows 11 to instantly match and bind
      UsbNcm.sys.
  2. Systemd Boot Service:
      • Created /etc/systemd/system/pi-usb-gadget.service (enabled in sysinit.target).
      • Runs early in boot before NetworkManager.service, ensuring the gadget interface is already present when
      NetworkManager starts.
  3. Kernel Modules & Boot Command Line:
      • Created /etc/modules-load.d/pi-usb-gadget.conf loading dwc2, libcomposite, and usb_f_ncm.
      • Cleaned /boot/firmware/cmdline.txt to remove g_ether while retaining modules-load=dwc2.
      • Preserved /boot/firmware/config.txt with dtoverlay=dwc2,dr_mode=peripheral.
  4. NetworkManager & Routing Isolation:
      • Created /etc/NetworkManager/conf.d/10-manage-usb0.conf to guarantee usb0 is managed by NetworkManager.
      • Updated NetworkManager connection Pi USB:
          • ipv4.method: shared (Pi runs DHCP on 10.42.0.0/24 with Pi IP 10.42.0.1).
          • ipv4.never-default: yes (Guarantees the Pi never treats usb0 as its internet gateway).
      • Created /etc/NetworkManager/dnsmasq-shared.d/no-gateway.conf (dhcp-option=3):
          • Prevents NetworkManager's DHCP server from pushing a default gateway to your Windows laptop.
          • Result: Windows routes internet traffic through its normal Wi-Fi, while traffic for 10.42.0.0/24 routes
          over the USB cable.


  ──────
  ## 3. End-to-End Verification Results

  Following a full system reboot of the Raspberry Pi:

   Test                       │ Target                  │ Result     │ Details
  ────────────────────────────┼─────────────────────────┼────────────┼───────────────────────────────────────────────
   Windows Device Recognition │ UsbNcm Host Device      │ OK         │ Bound to UsbNcm.sys, 0 problem codes
   Windows Link Speed         │ Ethernet 3              │ 426.0 Mbps │ High-speed USB link
   Windows DHCP Lease         │ 10.42.0.188/24          │ OK         │ Received from Pi; default gateway omitted
   USB Ping Latency           │ 10.42.0.1               │ < 1 ms     │ Average 0–1 ms over USB cable
   SSH over USB IP            │ benjamin@10.42.0.1      │ Connected  │ SSH key and password authentication working
   SSH over mDNS              │ benjamin@raspberrypi.lo │ Connected  │ Resolves to 10.42.0.1
                              │ cal                     │            │
   VNC Port 5900              │ 10.42.0.1:5900          │ Reachable  │ TigerVNC / VNC desktop link active
   SCP / File Transfer        │ 10.42.0.1               │ Success    │ Bi-directional file transfer verified
   Pi Wi-Fi (wlan0)           │ 192.168.0.125           │ Connected  │ TPLink active, default internet route on Wi-
                              │                         │            │ Fi
   Laptop Wi-Fi               │ 192.168.0.197           │ Connected  │ Laptop internet traffic flows over home Wi-Fi
   Reboot Persistence         │ Reboot test             │ Verified   │ Auto-starts cleanly on cold/warm boot
  ──────
  ## 4. How to Use Your Connection

  Whenever you plug the USB-C cable between your Windows laptop and Raspberry Pi 5:

  • SSH:
    ssh benjamin@10.42.0.1
    # or
    ssh benjamin@raspberrypi.local

  • VNC:
  Open TigerVNC Viewer on Windows and connect to:
    10.42.0.1:5900
    # or
    raspberrypi.local:5900

  • SFTP / File Transfer:
  Connect FileZilla / WinSCP / Cyberduck to host 10.42.0.1, port 22, user benjamin.