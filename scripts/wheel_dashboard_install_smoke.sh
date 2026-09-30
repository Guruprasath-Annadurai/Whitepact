#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# WS-1: verify built wheel with [dashboard] supports sovereign doctor.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "${WORKDIR}"' EXIT

echo "== wheel smoke ([dashboard] extra) =="
echo "python: ${PYTHON}"

unset PYTHONPATH

"${PYTHON}" -m venv "${WORKDIR}/venv"
# shellcheck disable=SC1091
source "${WORKDIR}/venv/bin/activate"
python -m pip install -q -U pip build
python -m build -o "${WORKDIR}/dist" "${ROOT}"
wheel_path="$(echo "${WORKDIR}/dist/"*.whl)"
python -m pip install -q "${wheel_path}[dashboard]"

whitepact --help | grep -q "doctor"
whitepact doctor --json | grep -q '"checks"'

echo "wheel [dashboard] install smoke: PASS"
