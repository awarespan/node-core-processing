# Volunteer Portal — LAN demonstration setup

The temporary volunteer portal is built and served by the Node's existing volunteer gateway. It is not a separate cloud service.

## Install / update

1. Run `./scripts/setup.sh` and `./scripts/install.sh` as documented in the root README.
2. Reserve a stable LAN IP for the Pi in the Wi-Fi router (DHCP reservation recommended).
3. Generate the LAN HTTPS certificate for that IP:

   ```bash
   ./scripts/setup-lan-https.sh 192.168.1.50
   ```

4. On each Android device, open `https://<PI-LAN-IP>:8443/awarespan-lan-ca.crt`, download the certificate, then install it under **Settings → Security → Encryption & credentials → Install a certificate → CA certificate**. Android wording varies by vendor/version. This is necessary because browser camera access requires a secure context; plain HTTP on a LAN IP is not sufficient.
5. Set `VOLUNTEER_GATEWAY_TLS=true` in the node `.env`, then restart `awarespan-node.service`.
6. Open `https://<PI-LAN-IP>:8443/` from a phone/laptop on the same non-isolated Wi-Fi network.

The portal uses its own origin for the HTTP authentication endpoint and volunteer WebSocket. The node inference/dashboard WebSocket remains on port `8766`, so both `8443/tcp` and `8766/tcp` must be reachable from LAN clients. Do not expose either port to the public internet for this demo.

## Camera and microphone

The browser asks for camera permission only after the operator initiates a session. Frames are JPEG-compressed and downscaled in-browser before transmission. The Pi owns inference and deterrence. Browser microphone donation remains unavailable until the node audio ingestion/classification pipeline is implemented; the UI must not imply otherwise.

## Network checks

- Phone and Pi must be on the same LAN; guest Wi-Fi/client isolation can block peer access.
- Verify `https://<PI-LAN-IP>:8443/` and `wss://<PI-LAN-IP>:8766/health` are reachable.
- If the Pi IP changes, regenerate the certificate for the new IP and reinstall the CA only if the CA itself changed.
