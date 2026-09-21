#!/usr/bin/env bash
# Disposable PostgreSQL helpers for release validation (localhost only).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${ROOT}/docker-compose.release-test.yml"
export WHITEPACT_TEST_PG_ADMIN_URL="${WHITEPACT_TEST_PG_ADMIN_URL:-postgresql://wp:wp@127.0.0.1:55432/postgres}"

cmd="${1:-}"
case "${cmd}" in
  start)
    docker compose -f "${COMPOSE_FILE}" up -d postgres
    ;;
  wait)
    docker compose -f "${COMPOSE_FILE}" exec -T postgres pg_isready -U wp -d postgres
    ;;
  stop)
    docker compose -f "${COMPOSE_FILE}" stop postgres
    ;;
  down)
    docker compose -f "${COMPOSE_FILE}" down
    ;;
  reset)
    docker compose -f "${COMPOSE_FILE}" down -v
    docker compose -f "${COMPOSE_FILE}" up -d postgres
    "${BASH_SOURCE[0]}" wait
    ;;
  url)
    echo "${WHITEPACT_TEST_PG_ADMIN_URL}"
    ;;
  *)
    echo "Usage: $0 {start|wait|stop|down|reset|url}" >&2
    exit 2
    ;;
esac
