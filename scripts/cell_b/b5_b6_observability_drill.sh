#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${ROOT}/artifacts/production/b5-b6-observability-drill.json"
SHA="$(git rev-parse HEAD)"
mkdir -p "$(dirname "$OUT")"

# Induce Prometheus-visible errors locally (no long-running stack required).
python3 - <<'PY' "$OUT" "$SHA"
import json, sys
from pathlib import Path
from fastapi.testclient import TestClient
from responsibleai.dashboard.app import app
from responsibleai.dashboard.prometheus import observe_request

client = TestClient(app)
observe_request("/api/health", 500)
body = client.get("/metrics").text
ok = "rai_requests_total" in body and "status=\"500\"" in body or "status='500'" in body
Path(sys.argv[1]).write_text(json.dumps({
  "phase": "B5_B6",
  "source_sha": sys.argv[2],
  "metrics_error_induction": ok,
  "alert_rules_file": "grafana/prometheus/alert-rules.yml",
  "prometheus_stack_deployed": False,
  "alertmanager_fired": False,
  "otel_collector_export_verified": False,
  "limitations": "Full Prometheus/Alertmanager/OTel collector stack not exercised in zero-cost VM"
}, indent=2) + "\n")
print("wrote", sys.argv[1])
PY
