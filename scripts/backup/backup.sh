#!/usr/bin/env bash
# Yoohoo Database Backup Script
# Runs via cron: 0 2 * * * /opt/yoohoo/scripts/backup/backup.sh
set -euo pipefail

# ─── Configuration ───
BACKUP_DIR="${BACKUP_DIR:-/opt/yoohoo/backups}"
COMPOSE_DIR="${COMPOSE_DIR:-/opt/yoohoo}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-yoohoo-postgres-1}"
POSTGRES_USER="${POSTGRES_USER:-yoohoo}"

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

# ─── Weekly copy (every Sunday) ───
if [ "$WEEKDAY" -eq 7 ]; then
  cp "$DAILY_DIR/$FILENAME" "$WEEKLY_DIR/$FILENAME"
  echo "[$(date)] Weekly backup copied"
fi

# ─── Monthly copy (1st of month) ───
if [ "$DATE" -eq "01" ]; then
  cp "$DAILY_DIR/$FILENAME" "$MONTHLY_DIR/$FILENAME"
  echo "[$(date)] Monthly backup copied"
fi

# ─── Retention cleanup ───
cleanup_old() {
  local dir=$1
  local keep=$2
  local count
  count=$(find "$dir" -name "yoohoo_*.sql.gz" -type f | wc -l)
  if [ "$count" -gt "$keep" ]; then
    find "$dir" -name "yoohoo_*.sql.gz" -type f \
      | sort | head -n $(( count - keep )) \
      | xargs rm -f
    echo "[$(date)] Cleaned up $(( count - keep )) old backups in $dir"
  fi
}

cleanup_old "$DAILY_DIR" "$DAILY_KEEP"
cleanup_old "$WEEKLY_DIR" "$WEEKLY_KEEP"
cleanup_old "$MONTHLY_DIR" "$MONTHLY_KEEP"

echo "[$(date)] Backup completed successfully"
