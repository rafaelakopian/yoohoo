#!/usr/bin/env bash
# Migrate all provisioned tenant databases.
# Exits non-zero if ANY tenant migration fails — deploy workflow will fail.
set -euo pipefail

cd "$(dirname "$0")/.."

# Source .env for POSTGRES_USER (if available)
# shellcheck disable=SC1091
source .env 2>/dev/null || true

PG_USER="${POSTGRES_USER:-yoohoo}"

# Query all provisioned tenant slugs from central DB
SLUGS=$(docker compose exec -T postgres psql -U "$PG_USER" -d ps_core_db \
  -t -A -c "SELECT slug FROM tenants WHERE is_provisioned = true" 2>/dev/null || true)

if [ -z "$SLUGS" ]; then
  echo "No provisioned tenants found — skipping tenant migrations"
  exit 0
fi

FAILED=()
COUNT=0

for slug in $SLUGS; do
  COUNT=$((COUNT + 1))
  echo "--- Migrating tenant [$COUNT]: $slug ---"
  if ! docker compose exec -T api alembic \
    -x mode=tenant -x "tenant_slug=$slug" upgrade tenant@head; then
    echo "ERROR: Migration FAILED for tenant: $slug"
    FAILED+=("$slug")
  fi
done

echo ""
echo "=== Tenant migrations: $COUNT total, ${#FAILED[@]} failed ==="

if [ ${#FAILED[@]} -gt 0 ]; then
  echo "FAILED TENANTS: ${FAILED[*]}"
  exit 1
fi

echo "All tenant migrations completed successfully"
