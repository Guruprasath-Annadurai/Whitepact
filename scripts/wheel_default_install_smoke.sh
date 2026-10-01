#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# WS-1: verify built wheel installs without [dashboard] and whitepact core CLI works.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "${WORKDIR}"' EXIT

# Must match whitepact.cli._OPTIONAL_SOVEREIGN_HINT (Click prefixes with "Error: ").
EXPECTED_DOCTOR_GUIDANCE="This command requires optional dashboard dependencies. Install with: pip install 'rai-governance-platform[dashboard]'"
EXPECTED_DOCTOR_EXIT=1

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

set +e
doctor_out="$(whitepact doctor --json 2>&1)"
doctor_status=$?
set -euo pipefail

if [[ "${doctor_status}" -eq 0 ]]; then
  echo "whitepact doctor --json must not succeed without [dashboard] extras" >&2
  echo "${doctor_out}" >&2
  exit 1
fi

if [[ "${doctor_status}" -ne "${EXPECTED_DOCTOR_EXIT}" ]]; then
  echo "whitepact doctor --json exit ${doctor_status}; expected ${EXPECTED_DOCTOR_EXIT}" >&2
  echo "${doctor_out}" >&2
  exit 1
fi

if echo "${doctor_out}" | grep -q "Traceback (most recent call last)"; then
  echo "whitepact doctor --json must not emit a Python traceback" >&2
  echo "${doctor_out}" >&2
  exit 1
fi

if ! echo "${doctor_out}" | grep -qF "${EXPECTED_DOCTOR_GUIDANCE}"; then
  echo "whitepact doctor --json missing expected installation guidance" >&2
  echo "expected substring: ${EXPECTED_DOCTOR_GUIDANCE}" >&2
  echo "${doctor_out}" >&2
  exit 1
fi

echo "doctor without extras: exit ${doctor_status}, guidance ok, no traceback"
echo "wheel default-install smoke: PASS"
