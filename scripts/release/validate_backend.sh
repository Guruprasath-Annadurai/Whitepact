#!/usr/bin/env bash
# Preliminary backend validation harness (PREPARATION — not a final release verdict).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

ARTIFACT_DIR="${ROOT}/artifacts/release-validation/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "${ARTIFACT_DIR}"
LOG="${ARTIFACT_DIR}/validate_backend.log"
exec > >(tee -a "${LOG}") 2>&1

export WHITEPACT_TEST_PG_ADMIN_URL="${WHITEPACT_TEST_PG_ADMIN_URL:-postgresql://wp:wp@127.0.0.1:55432/postgres}"
export RAI_AUTO_MIGRATE="${RAI_AUTO_MIGRATE:-false}"
export RAI_AUTH_ENABLED="${RAI_AUTH_ENABLED:-true}"
export RAI_DB_URL=""

echo "=== WhitePact release backend validation (preparation) ==="
echo "Artifacts: ${ARTIFACT_DIR}"

if ! python3 -c "import asyncpg" 2>/dev/null; then
  echo "Installing project with dev + dashboard + postgres extras..."
  python3 -m pip install -q -e ".[dev,dashboard,postgres,sso,sentiment,mcp]"
else
  python3 -m pip install -q -e ".[dev,dashboard,postgres,sso,sentiment,mcp]"
fi

if ! "${ROOT}/scripts/release/postgres_disposable.sh" wait 2>/dev/null; then
  echo "Starting disposable PostgreSQL via docker compose..."
  "${ROOT}/scripts/release/postgres_disposable.sh" start
  for _ in $(seq 1 40); do
    if "${ROOT}/scripts/release/postgres_disposable.sh" wait 2>/dev/null; then
      break
    fi
    sleep 1
  done
  "${ROOT}/scripts/release/postgres_disposable.sh" wait
fi

echo "=== Alembic heads ==="
alembic heads | tee "${ARTIFACT_DIR}/alembic_heads.txt"

echo "=== Migration + postgres-focused tests ==="
pytest tests/test_postgres_migrations.py tests/test_db_migrate.py tests/test_auth_real_postgres.py \
  tests/test_mcp_production_tool_registry.py \
  -q --tb=short | tee "${ARTIFACT_DIR}/pytest_focused.txt"

echo "=== Broader backend slice (may fail — classified in report) ==="
set +e
pytest tests/ -q --ignore=tests/release_blackbox --maxfail=50 \
  --tb=line 2>&1 | tee "${ARTIFACT_DIR}/pytest_broad.txt"
BROAD_EXIT=$?
set -e

echo "Broad suite exit code: ${BROAD_EXIT}"
echo "Log directory: ${ARTIFACT_DIR}"
exit "${BROAD_EXIT}"
