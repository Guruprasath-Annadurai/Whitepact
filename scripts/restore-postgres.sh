#!/usr/bin/env bash
# Restore a Postgres backup produced by scripts/backup-postgres.sh.
#
# Usage:
#   ./scripts/restore-postgres.sh <backup_file.sql.gz>
#
# WARNING: this drops and recreates the target database. Confirms before
# proceeding. Intended for disaster recovery or standing up a staging
# replica from a production snapshot — not a routine operation.

set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.prod}"
BACKUP_FILE="${1:?Usage: $0 <backup_file.sql.gz>}"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "ERROR: backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found. Run from the repo root, or set ENV_FILE." >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

DB="${POSTGRES_DB:-responsibleai}"
USER="${POSTGRES_USER:-rai_user}"

echo "This will DROP and recreate database '$DB' from $BACKUP_FILE."
echo "All current data in '$DB' will be permanently lost."
read -r -p "Type the database name to confirm ($DB): " CONFIRM
if [ "$CONFIRM" != "$DB" ]; then
  echo "Confirmation did not match. Aborting — nothing was changed."
  exit 1
fi

echo "[$(date -u +%FT%TZ)] Stopping app services (keeping postgres up)..."
docker compose -f "$COMPOSE_FILE" stop dashboard mcp-http

echo "[$(date -u +%FT%TZ)] Dropping and recreating database..."
docker compose -f "$COMPOSE_FILE" exec -T postgres \
  psql -U "$USER" -d postgres -c "DROP DATABASE IF EXISTS ${DB};"
docker compose -f "$COMPOSE_FILE" exec -T postgres \
  psql -U "$USER" -d postgres -c "CREATE DATABASE ${DB} OWNER ${USER};"

echo "[$(date -u +%FT%TZ)] Restoring from backup..."
gunzip -c "$BACKUP_FILE" | docker compose -f "$COMPOSE_FILE" exec -T postgres \
  psql -U "$USER" -d "$DB"

echo "[$(date -u +%FT%TZ)] Restarting app services..."
docker compose -f "$COMPOSE_FILE" up -d dashboard mcp-http

echo "[$(date -u +%FT%TZ)] Restore complete. Verify with:"
echo "  curl -s https://<your-domain>/api/health"
echo "  docker compose -f $COMPOSE_FILE exec dashboard alembic current"
