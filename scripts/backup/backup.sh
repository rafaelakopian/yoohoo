#!/usr/bin/env bash
# Yoohoo Database Backup Script
# Runs via cron: 0 2 * * * /opt/yoohoo/scripts/backup/backup.sh
set -euo pipefail

# ─── Configuration ───
BACKUP_DIR="${BACKUP_DIR:-/opt/yoohoo/backups}"
COMPOSE_DIR="${COMPOSE_DIR:-/opt/yoohoo}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-yoohoo-postgres-1}"
POSTGRES_USER="${POSTGRES_USER:-yoohoo}"
BACKUP_KEY_FILE="${BACKUP_KEY_FILE:-/opt/yoohoo/.backup-key}"
BACKUP_REMOTE="${BACKUP_REMOTE:-}"

# Retention policy
DAILY_KEEP=7
WEEKLY_KEEP=4
MONTHLY_KEEP=3

# ─── Directories ───
DAILY_DIR="$BACKUP_DIR/daily"
WEEKLY_DIR="$BACKUP_DIR/weekly"
MONTHLY_DIR="$BACKUP_DIR/monthly"
mkdir -p "$DAILY_DIR" "$WEEKLY_DIR" "$MONTHLY_DIR"

# ─── Timestamp ───
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE=$(date +%d)
WEEKDAY=$(date +%u)  # 1=Monday, 7=Sunday
FILENAME="yoohoo_${TIMESTAMP}.sql.gz"

echo "[$(date)] Starting database backup..."

# ─── Dump ───
docker exec "$POSTGRES_CONTAINER" pg_dumpall -U "$POSTGRES_USER" \
  | gzip > "$DAILY_DIR/$FILENAME"

FILESIZE=$(du -h "$DAILY_DIR/$FILENAME" | cut -f1)
echo "[$(date)] Backup created: $FILENAME ($FILESIZE)"

# ─── GPG Encryption (if key file exists) ───
BACKUP_FILE="$DAILY_DIR/$FILENAME"
if [ -f "$BACKUP_KEY_FILE" ]; then
  gpg --batch --yes --symmetric --cipher-algo AES256 \
    --passphrase-file "$BACKUP_KEY_FILE" "$BACKUP_FILE"
  rm "$BACKUP_FILE"
  BACKUP_FILE="${BACKUP_FILE}.gpg"
  FILENAME="${FILENAME}.gpg"
  echo "[$(date)] Backup encrypted with AES-256"
fi

# ─── SHA256 Integrity Hash ───
sha256sum "$BACKUP_FILE" > "${BACKUP_FILE}.sha256"

# ─── Weekly copy (every Sunday) ───
if [ "$WEEKDAY" -eq 7 ]; then
  cp "$BACKUP_FILE" "$WEEKLY_DIR/$FILENAME"
  cp "${BACKUP_FILE}.sha256" "$WEEKLY_DIR/${FILENAME}.sha256"
  echo "[$(date)] Weekly backup copied"
fi

# ─── Monthly copy (1st of month) ───
if [ "$DATE" -eq "01" ]; then
  cp "$BACKUP_FILE" "$MONTHLY_DIR/$FILENAME"
  cp "${BACKUP_FILE}.sha256" "$MONTHLY_DIR/${FILENAME}.sha256"
  echo "[$(date)] Monthly backup copied"
fi

# ─── Offsite Upload (hard fail if configured but fails) ───
if [ -n "$BACKUP_REMOTE" ]; then
  echo "[$(date)] Uploading to offsite storage..."
  rsync -az --timeout=60 "$BACKUP_FILE" "${BACKUP_FILE}.sha256" "${BACKUP_REMOTE}/"
  echo "[$(date)] Offsite upload completed"
fi

# ─── Retention cleanup ───
cleanup_old() {
  local dir=$1
  local keep=$2
  local pattern=$3
  local count
  count=$(find "$dir" -name "$pattern" -type f | wc -l)
  if [ "$count" -gt "$keep" ]; then
    find "$dir" -name "$pattern" -type f \
      | sort | head -n $(( count - keep )) \
      | xargs rm -f
    echo "[$(date)] Cleaned up $(( count - keep )) old backups in $dir"
  fi
}

# Clean up both .sql.gz and .sql.gz.gpg files + their .sha256 companions
cleanup_old "$DAILY_DIR" "$DAILY_KEEP" "yoohoo_*.sql.gz*"
cleanup_old "$WEEKLY_DIR" "$WEEKLY_KEEP" "yoohoo_*.sql.gz*"
cleanup_old "$MONTHLY_DIR" "$MONTHLY_KEEP" "yoohoo_*.sql.gz*"

echo "[$(date)] Backup completed successfully"
