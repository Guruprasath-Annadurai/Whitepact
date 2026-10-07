#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# Restore an encrypted WhitePact backup into a new staging database.
#
# The active database is not dropped. Cutover is a rename, and only when
# WHITEPACT_RESTORE_CUTOVER=1 is set after staging verification succeeds.
#
# Usage:
#   WHITEPACT_BACKUP_ENCRYPTION_KEY=... WHITEPACT_RESTORE_LOCAL=1 \
#     ./scripts/restore-postgres.sh backups/file.sql.gz.enc

set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.prod}"
BACKUP_FILE="${1:?Usage: $0 <backup.sql.gz.enc>}"
ACTIVE_DB="${PGDATABASE:-${POSTGRES_DB:-responsibleai}}"
OWNER="${PGUSER:-${POSTGRES_USER:-rai_user}}"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "ERROR: backup file not found: $BACKUP_FILE" >&2
  exit 2
fi

if [ "${WHITEPACT_RESTORE_LOCAL:-}" != "1" ]; then
  if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found." >&2
    exit 1
  fi
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  ACTIVE_DB="${POSTGRES_DB:-$ACTIVE_DB}"
  OWNER="${POSTGRES_USER:-$OWNER}"
fi

psql_admin() {
  if [ "${WHITEPACT_RESTORE_LOCAL:-}" = "1" ]; then
    psql -d postgres -v ON_ERROR_STOP=1 -X -q "$@"
  else
    docker compose -f "$COMPOSE_FILE" exec -T postgres \
      psql -U "$OWNER" -d postgres -v ON_ERROR_STOP=1 -X -q "$@"
  fi
}

psql_db() {
  local db="$1"
  shift
  if [ "${WHITEPACT_RESTORE_LOCAL:-}" = "1" ]; then
    psql -d "$db" -v ON_ERROR_STOP=1 -X -q "$@"
  else
    docker compose -f "$COMPOSE_FILE" exec -T postgres \
      psql -U "$OWNER" -d "$db" -v ON_ERROR_STOP=1 -X -q "$@"
  fi
}

WORK="$(mktemp -d)"
chmod 700 "$WORK"
cleanup() {
  rm -rf "$WORK"
}
trap cleanup EXIT

PYTHON="${WHITEPACT_PYTHON:-python3}"
if ! PLAN="$("$PYTHON" -m responsibleai.ops prepare-restore --backup "$BACKUP_FILE" --work "$WORK")"; then
  echo "ERROR: backup failed validation. The active database was not modified." >&2
  exit 2
fi

STAGING="$("$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["staging_database"])' <<<"$PLAN")"
PLAIN="$("$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["plain_path"])' <<<"$PLAN")"
mapfile -t RELATIONS < <("$PYTHON" -c 'import json,sys; print("\n".join(json.load(sys.stdin)["required_relations"]))' <<<"$PLAN")
if ! [[ "$STAGING" =~ ^[A-Za-z_][A-Za-z0-9_]{0,62}$ ]]; then
  echo "ERROR: staging name rejected" >&2
  exit 2
fi
if ! [[ "$OWNER" =~ ^[A-Za-z_][A-Za-z0-9_]{0,62}$ ]]; then
  echo "ERROR: database owner is not a safe identifier" >&2
  exit 2
fi

echo "[$(date -u +%FT%TZ)] Creating staging database ${STAGING}"
psql_admin -c "CREATE DATABASE \"${STAGING}\" OWNER \"${OWNER}\";"

restore_ok=0
if psql_db "$STAGING" <"$PLAIN"; then
  restore_ok=1
fi

if [ "$restore_ok" -ne 1 ]; then
  echo "ERROR: restore into staging failed. Dropping staging only." >&2
  psql_admin -c "DROP DATABASE IF EXISTS \"${STAGING}\" WITH (FORCE);" || true
  exit 1
fi

for rel in "${RELATIONS[@]}"; do
  if [ -z "$rel" ]; then
    continue
  fi
  if ! [[ "$rel" =~ ^[A-Za-z_][A-Za-z0-9_]{0,62}$ ]]; then
    echo "ERROR: required relation name rejected. Dropping staging only." >&2
    psql_admin -c "DROP DATABASE IF EXISTS \"${STAGING}\";" || true
    exit 1
  fi
  present="$(psql_db "$STAGING" -tAc "SELECT to_regclass('public.${rel}') IS NOT NULL;" | tr -d '[:space:]')"
  if [ "$present" != "t" ]; then
    echo "ERROR: staging is missing required relation ${rel}. Dropping staging only." >&2
    psql_admin -c "DROP DATABASE IF EXISTS \"${STAGING}\" WITH (FORCE);" || true
    exit 1
  fi
done

echo "[$(date -u +%FT%TZ)] Staging restore verified: ${STAGING}"
echo "Active database ${ACTIVE_DB} was not dropped."

if [ "${WHITEPACT_RESTORE_CUTOVER:-}" != "1" ]; then
  echo "Cutover was not requested. Staging database left in place."
  exit 0
fi

PREVIOUS="${ACTIVE_DB}_prev_$(date -u +%Y%m%d%H%M%S)"
echo "[$(date -u +%FT%TZ)] Renaming ${ACTIVE_DB} to ${PREVIOUS} and ${STAGING} to ${ACTIVE_DB}"
if ! psql_admin -c "ALTER DATABASE \"${ACTIVE_DB}\" RENAME TO \"${PREVIOUS}\";"; then
  echo "ERROR: cutover rename of the active database failed. Staging remains ${STAGING}." >&2
  exit 1
fi
if ! psql_admin -c "ALTER DATABASE \"${STAGING}\" RENAME TO \"${ACTIVE_DB}\";"; then
  echo "ERROR: staging rename failed. Restoring the previous database name." >&2
  psql_admin -c "ALTER DATABASE \"${PREVIOUS}\" RENAME TO \"${ACTIVE_DB}\";" || true
  exit 1
fi
echo "[$(date -u +%FT%TZ)] Cutover complete. Previous database kept as ${PREVIOUS}."
