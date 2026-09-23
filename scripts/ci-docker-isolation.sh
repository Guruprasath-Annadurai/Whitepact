#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
#
# Reproducible Docker isolation verification for WhitePact V1.
# Requires a working Docker daemon (docker info) and the project venv.
#
# Covers:
#   network disabled, CPU/memory/PID limits, filesystem/workspace isolation,
#   ownership, cleanup, timeout/kill behavior.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null 2>&1; then
  echo "docker binary not found" >&2
  exit 2
fi
if ! docker info >/dev/null 2>&1; then
  echo "docker daemon is not reachable" >&2
  exit 2
fi

python -m pytest \
  tests/test_docker_container_lifecycle.py \
  tests/test_docker_ownership_regression.py \
  tests/test_runtime_isolation_docker.py \
  tests/test_runtime_isolation_hardgate.py \
  tests/test_runtime_isolation_stress.py \
  -q --tb=short
