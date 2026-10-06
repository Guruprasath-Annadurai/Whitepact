#!/usr/bin/env bash
# WhitePact Cursor Cloud Agent — engineering bootstrap (install phase only).
# Does not start application services, disable auth, or touch cloud providers.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! python3 -m venv /tmp/_whitepact_venv_probe 2>/dev/null; then
  sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3-venv curl git
fi
rm -rf /tmp/_whitepact_venv_probe

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"

for cmd in python3 git terraform; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Required command missing after install: $cmd" >&2
    exit 1
  fi
done

echo "WhitePact Cursor Cloud Agent install complete (engineering bootstrap only)."
