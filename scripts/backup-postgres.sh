#!/usr/bin/env bash
# Backup the production Postgres database (docker-compose.prod.yml stack).
#
# Usage:
#   ./scripts/backup-postgres.sh [output_dir]
#
# Run via cron for scheduled backups, e.g. nightly at 2am:
#   0 2 * * * /path/to/ResponsibleAi/scripts/backup-postgres.sh /var/backups/rai >> /var/log/rai-backup.log 2>&1
#
# Restores with: ./scripts/restore-postgres.sh <backup_file>

set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.prod}"
OUTPUT_DIR="${1:-./backups}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_FILE="${OUTPUT_DIR}/responsibleai-${TIMESTAMP}.sql.gz"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found. Run from the repo root, or set ENV_FILE." >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

mkdir -p "$OUTPUT_DIR"

echo "[$(date -u +%FT%TZ)] Starting backup -> $BACKUP_FILE"

docker compose -f "$COMPOSE_FILE" exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-rai_user}" -d "${POSTGRES_DB:-responsibleai}" --format=plain \
  | gzip > "$BACKUP_FILE"

if [ ! -s "$BACKUP_FILE" ]; then
  echo "ERROR: backup file is empty — pg_dump likely failed." >&2
  rm -f "$BACKUP_FILE"
  exit 1
fi

echo "[$(date -u +%FT%TZ)] Backup complete: $(du -h "$BACKUP_FILE" | cut -f1)"

# Prune backups older than RETENTION_DAYS.
find "$OUTPUT_DIR" -name "responsibleai-*.sql.gz" -mtime "+${RETENTION_DAYS}" -print -delete

echo "[$(date -u +%FT%TZ)] Retention: keeping backups from the last ${RETENTION_DAYS} days."
