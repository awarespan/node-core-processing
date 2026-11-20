#!/usr/bin/env bash
# Create a local CA and IP-SAN server certificate for the LAN volunteer portal.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERT_DIR="${ROOT}/state/certs"
STATIC_DIR="${ROOT}/static/volunteer"
LAN_IP="${1:-$(hostname -I 2>/dev/null | awk '{print $1}')}"
if [[ -z "${LAN_IP}" ]]; then
  echo "Could not determine LAN IP. Usage: $0 <LAN-IP>" >&2
  exit 2
fi
mkdir -p "${CERT_DIR}" "${STATIC_DIR}"
chmod 700 "${CERT_DIR}"
cat > "${CERT_DIR}/server.ext" <<EXT
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=IP:${LAN_IP},DNS:awarespan.local
EXT
if [[ ! -s "${CERT_DIR}/awarespan-lan-ca.crt" || ! -s "${CERT_DIR}/awarespan-lan-ca.key" ]]; then
  openssl req -x509 -newkey rsa:3072 -nodes -sha256 -days 3650 \
    -keyout "${CERT_DIR}/awarespan-lan-ca.key" \
    -out "${CERT_DIR}/awarespan-lan-ca.crt" \
    -subj "/CN=AWARESPAN LAN Demo CA/O=AWARESPAN" \
    -addext "basicConstraints=critical,CA:TRUE" \
    -addext "keyUsage=critical,keyCertSign,cRLSign" >/dev/null 2>&1
  chmod 600 "${CERT_DIR}/awarespan-lan-ca.key"
fi
openssl req -new -newkey rsa:2048 -nodes -sha256 \
  -keyout "${CERT_DIR}/volunteer_gateway.key" \
  -out "${CERT_DIR}/volunteer_gateway.csr" \
  -subj "/CN=${LAN_IP}/O=AWARESPAN" >/dev/null 2>&1
openssl x509 -req -sha256 -days 825 \
  -in "${CERT_DIR}/volunteer_gateway.csr" \
  -CA "${CERT_DIR}/awarespan-lan-ca.crt" \
  -CAkey "${CERT_DIR}/awarespan-lan-ca.key" -CAcreateserial \
  -out "${CERT_DIR}/volunteer_gateway.crt" \
  -extfile "${CERT_DIR}/server.ext" >/dev/null 2>&1
chmod 600 "${CERT_DIR}/volunteer_gateway.key"
chmod 644 "${CERT_DIR}/volunteer_gateway.crt" "${CERT_DIR}/awarespan-lan-ca.crt"
cp "${CERT_DIR}/awarespan-lan-ca.crt" "${STATIC_DIR}/awarespan-lan-ca.crt"
echo "LAN HTTPS certificate ready for https://${LAN_IP}:8443"
echo "Install ${STATIC_DIR}/awarespan-lan-ca.crt as a CA certificate on each demo Android device."
