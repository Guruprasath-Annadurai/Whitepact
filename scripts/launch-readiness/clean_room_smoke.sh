#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# Clean-room smoke: isolated tree from git archive, fresh venv, no editable reuse.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HEAD_SHA="$(git -C "$ROOT" rev-parse HEAD)"
WORK="$(mktemp -d -t whitepact-clean-room-XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

echo "== WhitePact clean-room smoke =="
echo "Source HEAD: $HEAD_SHA"
echo "Extract: $WORK"

if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: python3 not found"
  exit 1
fi

python3 -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'

git -C "$ROOT" archive "$HEAD_SHA" | tar -x -C "$WORK"
cd "$WORK"

python3 -m venv .venv-clean
# shellcheck disable=SC1091
source .venv-clean/bin/activate
pip install -U pip -q
pip install -e ".[dashboard]" -q

echo "-- quickstart_stranger_authority --"
python examples/quickstart_stranger_authority.py

echo "-- pytest workflow authority (subset) --"
pip install pytest pytest-cov pytest-asyncio -q
PYTEST_ADDOPTS= pytest tests/test_workflow_authority.py -q --tb=no -o addopts=

echo "PASS: clean-room smoke completed from archive $HEAD_SHA"
