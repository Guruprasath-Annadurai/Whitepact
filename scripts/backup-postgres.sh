#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# Dump Postgres, gzip it, and write only an authenticated encrypted artifact.
#
# Required: WHITEPACT_BACKUP_ENCRYPTION_KEY (Fernet key or passphrase).
# The key is never printed. Plaintext dumps are removed on success and failure.
#
# Local mode (tests and hosts with pg_dump):
#   WHITEPACT_BACKUP_LOCAL=1 PGHOST=... PGDATABASE=... ./scripts/backup-postgres.sh /tmp/out
# Docker Compose mode is the default when WHITEPACT_BACKUP_LOCAL is unset.

set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.prod}"
OUTPUT_DIR="${1:-./backups}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DATABASE="${PGDATABASE:-${POSTGRES_DB:-responsibleai}}"
TOOL_VERSION="${WHITEPACT_VERSION:-1.3.1}"

if [ -z "${WHITEPACT_BACKUP_ENCRYPTION_KEY:-}" ]; then
  echo "ERROR: WHITEPACT_BACKUP_ENCRYPTION_KEY is not set" >&2
  exit 2
fi

if [ "${WHITEPACT_BACKUP_LOCAL:-}" != "1" ] && [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found. Run from the repo root, or set WHITEPACT_BACKUP_LOCAL=1." >&2
  exit 1
fi

if [ "${WHITEPACT_BACKUP_LOCAL:-}" != "1" ]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  DATABASE="${POSTGRES_DB:-$DATABASE}"
fi

mkdir -p "$OUTPUT_DIR"
WORK="$(mktemp -d)"
chmod 700 "$WORK"
PLAIN="${WORK}/dump.sql"
install -m 0600 /dev/null "$PLAIN"
cleanup() {
  rm -rf "$WORK"
}
trap cleanup EXIT

echo "[$(date -u +%FT%TZ)] Starting encrypted backup"

if [ "${WHITEPACT_BACKUP_LOCAL:-}" = "1" ]; then
  pg_dump --format=plain --no-owner --dbname="${PGDATABASE:?PGDATABASE is required}" >"$PLAIN"
else
  docker compose -f "$COMPOSE_FILE" exec -T postgres \
    pg_dump -U "${POSTGRES_USER:-rai_user}" -d "$DATABASE" --format=plain \
    >"$PLAIN"
fi

if [ ! -s "$PLAIN" ]; then
  echo "ERROR: pg_dump produced an empty file." >&2
  exit 1
fi

DEST="${OUTPUT_DIR}/responsibleai-${TIMESTAMP}.sql.gz.enc"
RELATIONS=()
if [ -n "${WHITEPACT_BACKUP_REQUIRED_RELATIONS:-}" ]; then
  IFS=',' read -r -a RELATIONS <<< "${WHITEPACT_BACKUP_REQUIRED_RELATIONS}"
fi
PYTHON="${WHITEPACT_PYTHON:-python3}"
ARGS=("$PYTHON" -m responsibleai.ops encrypt --input "$PLAIN" --output "$DEST" --database "$DATABASE" --tool-version "$TOOL_VERSION")
for rel in "${RELATIONS[@]}"; do
  ARGS+=(--relation "$rel")
done
"${ARGS[@]}"
rm -f "$PLAIN"

if [ -e "${OUTPUT_DIR}/responsibleai-${TIMESTAMP}.sql.gz" ]; then
  echo "ERROR: plaintext gzip was created; refusing to leave it in place." >&2
  rm -f "${OUTPUT_DIR}/responsibleai-${TIMESTAMP}.sql.gz"
  exit 1
fi

echo "[$(date -u +%FT%TZ)] Encrypted backup written: ${DEST}"
echo "[$(date -u +%FT%TZ)] Manifest: ${DEST}.manifest.json"
