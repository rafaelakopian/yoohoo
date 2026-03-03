#!/usr/bin/env bash
# Called by certbot --post-hook (runs as root).
# Only copies certificates and sets permissions.
# Does NOT call docker — nginx reload is handled separately by deploy user.
set -euo pipefail

CERT_DIR="/etc/letsencrypt/live/yoohoo"
SSL_DIR="/opt/yoohoo/ssl"

if [ ! -d "$CERT_DIR" ]; then
  echo "ERROR: Certificate directory not found: $CERT_DIR" >&2
  exit 1
fi

cp "$CERT_DIR/fullchain.pem" "$SSL_DIR/fullchain.pem"
cp "$CERT_DIR/privkey.pem" "$SSL_DIR/privkey.pem"

chmod 644 "$SSL_DIR/fullchain.pem"
chmod 600 "$SSL_DIR/privkey.pem"

# Signal file for nginx-reload-if-renewed.sh (runs as deploy user)
touch "$SSL_DIR/.renewed"

echo "$(date -Iseconds) Certificates copied to $SSL_DIR"
