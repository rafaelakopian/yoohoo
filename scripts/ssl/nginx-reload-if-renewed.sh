#!/usr/bin/env bash
# Checks if SSL certificates were renewed and reloads nginx.
# Runs as deploy user via cron (no root required).
# Signal file (.renewed) is created by post-renew.sh (runs as root).
set -euo pipefail

SIGNAL="/opt/yoohoo/ssl/.renewed"

if [ -f "$SIGNAL" ]; then
  docker compose -f /opt/yoohoo/docker-compose.yml exec -T nginx nginx -s reload
  rm "$SIGNAL"
  echo "$(date -Iseconds) Nginx reloaded after certificate renewal"
fi
