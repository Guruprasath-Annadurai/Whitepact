#!/usr/bin/env bash
# Clean-room smoke: clone-agnostic when run from a fresh checkout.
# Does not start Docker or require API keys.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "== WhitePact clean-room smoke =="
echo "Root: $ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: python3 not found"
  exit 1
fi

PYVER="$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')"
echo "Python: $PYVER"
python3 -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'

if [[ ! -d .venv-smoke ]]; then
  python3 -m venv .venv-smoke
fi
# shellcheck disable=SC1091
source .venv-smoke/bin/activate
pip install -U pip -q
pip install -e ".[dashboard]" -q

echo "-- quickstart_stranger_authority --"
python examples/quickstart_stranger_authority.py

echo "-- pytest workflow authority (subset) --"
pip install pytest pytest-cov pytest-asyncio -q
PYTEST_ADDOPTS= pytest tests/test_workflow_authority.py -q --tb=no -o addopts=

echo "PASS: clean-room smoke completed"
