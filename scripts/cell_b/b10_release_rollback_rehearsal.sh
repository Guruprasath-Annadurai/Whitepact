#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# B10 — release metadata + blocked bad deploy + documented rollback path.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
OUT="${ROOT}/artifacts/production/b10-release-rollback-rehearsal.json"
SHA="$(git rev-parse HEAD)"
TREE="$(git rev-parse HEAD^{tree})"
CHART_VERSION="$(grep '^version:' helm/rai-governance/Chart.yaml | awk '{print $2}')"
START_TS="$(date -u +%FT%TZ)"

echo "[B10] validating good production values"
python -m responsibleai.operations.helm_validate helm/rai-governance/values-production.yaml
helm lint helm/rai-governance/ -f helm/rai-governance/values-production.yaml >/dev/null

echo "[B10] simulating blocked bad release (auth disabled)"
BAD_VALUES="$(mktemp)"
cp helm/rai-governance/values-production.yaml "$BAD_VALUES"
python - <<'PY' "$BAD_VALUES"
import sys, yaml
path = sys.argv[1]
data = yaml.safe_load(open(path, encoding="utf-8"))
data["config"]["authEnabled"] = False
yaml.safe_dump(data, open(path, "w", encoding="utf-8"))
PY
BLOCKED=0
if python -m responsibleai.operations.helm_validate "$BAD_VALUES"; then
  echo "ERROR: bad values unexpectedly passed validation"
  exit 1
else
  BLOCKED=1
fi
rm -f "$BAD_VALUES"

END_TS="$(date -u +%FT%TZ)"
mkdir -p "$(dirname "$OUT")"
python - <<PY
import json
from pathlib import Path
out = Path("$OUT")
out.write_text(json.dumps({
  "phase": "B10",
  "test": "release_rollback_rehearsal",
  "evidence_categories": ["CI_VERIFIED", "UNIT_TESTED"],
  "source_sha": "$SHA",
  "tree_sha": "$TREE",
  "chart_version": "$CHART_VERSION",
  "started_at": "$START_TS",
  "finished_at": "$END_TS",
  "good_release": {
    "helm_validate": "PASS",
    "helm_lint_production_overlay": "PASS",
    "immutable_source_sha_recorded": True
  },
  "bad_release_simulation": {
    "auth_disabled_values": "BLOCKED_BY_HELM_VALIDATE" if $BLOCKED else "FAIL",
    "deployed_to_cluster": False
  },
  "helm_rollback_rehearsal": {
    "status": "OWNER_ACTION_REQUIRED",
    "reason": "No disposable Kubernetes cluster in zero-cost qualification VM; use staging cluster procedure in docs/production/B10_ROLLBACK_PROCEDURE.md"
  },
  "limitations": "Binary rollback on cluster not executed in this environment."
}, indent=2) + "\\n", encoding="utf-8")
print("Wrote", out)
PY
