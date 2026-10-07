#!/usr/bin/env bash
# WhitePact Cursor Cloud Agent — start hook: readiness only (no app launch).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

for cmd in python3 git terraform; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Start readiness check failed: missing $cmd" >&2
    exit 1
  fi
done

echo "WhitePact Cloud Agent environment ready (no application services started)."
exit 0
