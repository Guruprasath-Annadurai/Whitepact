#!/usr/bin/env bash
# WS-1: verify built wheel installs without [dashboard] and whitepact core CLI works.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "${WORKDIR}"' EXIT

echo "== wheel smoke (default install) =="
echo "python: ${PYTHON}"
echo "root: ${ROOT}"

unset PYTHONPATH

"${PYTHON}" -m venv "${WORKDIR}/venv"
# shellcheck disable=SC1091
source "${WORKDIR}/venv/bin/activate"
python -m pip install -q -U pip build
python -m build -o "${WORKDIR}/dist" "${ROOT}"
python -m pip install -q "${WORKDIR}/dist/"*.whl

whitepact --help | grep -q "WhitePact"
whitepact --version | grep -q .
whitepact info | grep -q "rai-governance-platform"
biasbuster --help | grep -q "BiasBuster"

doctor_out="$(whitepact doctor --json 2>&1 || true)"
if echo "${doctor_out}" | grep -qi "dashboard"; then
  echo "doctor without extras reports dashboard install guidance (ok)"
else
  echo "expected doctor to mention dashboard optional dependencies" >&2
  echo "${doctor_out}" >&2
  exit 1
fi

echo "wheel default-install smoke: PASS"
