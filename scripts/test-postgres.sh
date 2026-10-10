#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# Manage the disposable PostgreSQL 16 used by the test suite (docker-compose.test.yml).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
COMPOSE=(docker compose -f docker-compose.test.yml)
URL="postgresql://wp:wp@127.0.0.1:55433/postgres"

case "${1:-}" in
  up)
    "${COMPOSE[@]}" up -d --wait
    echo "PostgreSQL 16 ready. Run: eval \"\$(scripts/test-postgres.sh env)\"" ;;
  env)
    echo "export WHITEPACT_TEST_PG_ADMIN_URL='${URL}'" ;;
  status)
    "${COMPOSE[@]}" ps ;;
  down)
    "${COMPOSE[@]}" down -v --remove-orphans ;;
  *)
    echo "usage: $0 {up|env|status|down}" >&2
    exit 2 ;;
esac
