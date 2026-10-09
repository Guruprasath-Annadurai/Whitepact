#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# M6 full regression gate (local/CI helper). No publish or deploy.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/src:${ROOT}/sdk/python:${PYTHONPATH:-}"
python -m pytest \
  tests/test_m6_final_engineering_campaign.py \
  tests/test_m5_integrated_regression_campaign.py \
  tests/test_m4_hostile_regression_campaign.py \
  tests/test_m4_postgres_assault_campaign.py \
  tests/test_totp_matched_counter_security.py \
  -q --tb=short "$@"
