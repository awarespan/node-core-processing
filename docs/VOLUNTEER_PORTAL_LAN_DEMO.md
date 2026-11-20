# Volunteer Portal — Linux and LAN demonstration

The volunteer portal is part of the Node runtime and is served by its volunteer gateway. It is not a separate cloud service and is not Raspberry-Pi-specific. Use the same repository and launcher on Ubuntu, Debian, Fedora, Raspberry Pi OS, or the Linux Codespace.

## Start on any Linux device

1. Clone the Node repository and run `./scripts/setup.sh --profile linux --no-train` (or the Pi profile on the Pi).
2. Build the portal if `static/volunteer/index.html` is missing or stale:

   ```bash
   cd web/volunteer-portal && npm ci && npm test && npm run build
   rsync -a --delete dist/ ../../static/volunteer/
   cd ../..
   ```

3. Start the complete node + portal:

   ```bash
   ./scripts/run-demo.sh
   ```

The launcher binds runtime and volunteer gateway to `0.0.0.0`, prints every detected LAN IPv4 address, and advertises the same `awarespan.local` name on the active device when Avahi is installed and running. The Linux setup wizard installs Avahi and enables its daemon on systemd hosts. Run only one node on a given LAN at a time. If mDNS is unavailable on a client, use the LAN IP printed by the launcher. Both TCP ports `8443` and `8766` must be reachable from the phone/client.

On the same host, `http://127.0.0.1:8443/` is a convenient local smoke-test URL. Browser camera/microphone APIs are only available in secure contexts; localhost is treated as secure, but a LAN IP over plain HTTP is not. For phone camera access:

1. On the active Linux host, run `./scripts/setup-lan-https.sh <LAN-IP>`.
2. Install `static/volunteer/awarespan-lan-ca.crt` on each Android test phone as a CA certificate (Android wording varies by version/vendor).
3. Set `VOLUNTEER_GATEWAY_TLS=true` in the repository `.env` and restart `./scripts/run-demo.sh`.
4. Open `https://awarespan.local:8443/` or `https://<LAN-IP>:8443/`.

The certificate includes both the specified IP and `awarespan.local`. Keep the CA private key in `state/certs/` (mode 0600); do not commit it. Re-running the certificate script with a different IP retains the existing local CA and reissues the host certificate.

## Codespace validation

The Codespace is a Linux validation target, not a separate product deployment. Start the launcher there and forward ports `8443` and `8766` as private ports. Open the forwarded HTTPS URL for port 8443; the portal uses that hostname for the gateway and runtime WebSocket. Codespace forwarding provides the browser-trusted HTTPS origin, so no local LAN CA installation is needed for this test. Do not make these ports public.

## Rebuild after portal edits

```bash
cd web/volunteer-portal
npm ci
npm test
npm run build
rsync -a --delete dist/ ../../static/volunteer/
```

## Media and hardware boundaries

The browser requests camera permission only after an operator initiates a session. Frames are JPEG-compressed and downscaled in-browser before transmission. Inference and deterrence execute on the active Node device; a Raspberry Pi is not required for portal or API validation. Microphone donation remains disabled until node-side audio ingestion/classification is implemented. Pi-only GPIO, CSI camera, speaker, thermal and power behaviour still require physical Pi validation.
