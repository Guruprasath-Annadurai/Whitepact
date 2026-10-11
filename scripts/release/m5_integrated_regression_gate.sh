#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# M5 integrated regression gate. Does not publish or deploy.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/src:${ROOT}/sdk/python:${PYTHONPATH:-}"
python -m pytest \
  tests/test_m5_integrated_regression_campaign.py \
  tests/test_m5_chaos_campaign_matrix.py \
  tests/test_m5_unknown_outcome_regression.py \
  tests/test_m5_revocation_stress_matrix.py \
  tests/test_m5_mcp_regression_index.py \
  tests/test_m4_m123_regression_index.py \
  -q --tb=short "$@"
