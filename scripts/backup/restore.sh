#!/usr/bin/env bash
# Yoohoo Database Restore Script
# Usage: ./restore.sh /path/to/backup.sql.gz[.gpg]
set -euo pipefail

COMPOSE_DIR="${COMPOSE_DIR:-/opt/yoohoo}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-yoohoo-postgres-1}"
POSTGRES_USER="${POSTGRES_USER:-yoohoo}"
BACKUP_KEY_FILE="${BACKUP_KEY_FILE:-/opt/yoohoo/.backup-key}"

if [ $# -ne 1 ]; then
  echo "Usage: $0 <backup-file.sql.gz[.gpg]>"
  exit 1
fi

BACKUP_FILE="$1"
if [ ! -f "$BACKUP_FILE" ]; then
  echo "Error: Backup file not found: $BACKUP_FILE"
  exit 1
fi

echo "=== YOOHOO DATABASE RESTORE ==="
echo "Backup: $BACKUP_FILE"
echo "This will REPLACE all databases on $POSTGRES_CONTAINER."
echo ""
read -p "Are you sure? (type 'yes' to confirm): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "Aborted."
  exit 0
fi

# ─── Integrity Check ───
if [ -f "${BACKUP_FILE}.sha256" ]; then
  echo "[$(date)] Verifying backup integrity..."
  if ! sha256sum -c "${BACKUP_FILE}.sha256"; then
    echo "INTEGRITY CHECK FAILED — backup may be corrupted!"
    exit 1
  fi
  echo "[$(date)] Integrity check passed"
fi

# ─── GPG Decryption (if .gpg extension) ───
RESTORE_FILE="$BACKUP_FILE"
TEMP_DECRYPTED=""
if [[ "$BACKUP_FILE" == *.gpg ]]; then
  if [ ! -f "$BACKUP_KEY_FILE" ]; then
    echo "Error: Backup is encrypted but key file not found: $BACKUP_KEY_FILE"
    exit 1
  fi
  TEMP_DECRYPTED="${BACKUP_FILE%.gpg}"
  echo "[$(date)] Decrypting backup..."
  gpg --batch --decrypt --passphrase-file "$BACKUP_KEY_FILE" \
    --output "$TEMP_DECRYPTED" "$BACKUP_FILE"
  RESTORE_FILE="$TEMP_DECRYPTED"
  echo "[$(date)] Backup decrypted"
fi

# ─── Restore ───
echo "[$(date)] Stopping API and worker..."
cd "$COMPOSE_DIR"
docker compose stop api worker

echo "[$(date)] Restoring database from $RESTORE_FILE..."
gunzip -c "$RESTORE_FILE" | docker exec -i "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" -d postgres

# Cleanup temp decrypted file
if [ -n "$TEMP_DECRYPTED" ] && [ -f "$TEMP_DECRYPTED" ]; then
  rm "$TEMP_DECRYPTED"
fi

echo "[$(date)] Starting API and worker..."
docker compose start api worker

echo "[$(date)] Waiting for health check..."
for i in 1 2 3 4 5; do
  if curl -sf http://localhost/health/ready > /dev/null 2>&1; then
    echo "[$(date)] Health check passed (attempt $i)"
    echo "[$(date)] Restore completed successfully"
    exit 0
  fi
  echo "Waiting... (attempt $i/5)"
  sleep 10
done

echo "[$(date)] WARNING: Health check failed after restore. Check logs!"
exit 1
