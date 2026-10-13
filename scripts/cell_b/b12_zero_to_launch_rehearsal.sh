#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# B12 — connected zero-to-launch rehearsal (SELF_REHEARSED).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
LOG="${ROOT}/artifacts/production/b12-zero-to-launch.jsonl"
SHA="$(git rev-parse HEAD)"
mkdir -p "$(dirname "$LOG")"
: >"$LOG"

log() { echo "{\"ts\":\"$(date -u +%FT%TZ)\",\"step\":\"$1\",\"status\":\"$2\"}" | tee -a "$LOG"; }

log "validate_dev_config" "start"
python -m responsibleai.operations.config_validate >/dev/null
log "validate_dev_config" "ok"

log "helm_production_contract" "start"
python -m responsibleai.operations.helm_validate helm/rai-governance/values-production.yaml
helm lint helm/rai-governance/ -f helm/rai-governance/values-production.yaml >/dev/null
log "helm_production_contract" "ok"

log "pytest_production_suite" "start"
pytest tests/production -q --no-cov
log "pytest_production_suite" "ok"

log "b10_release_rollback_script" "start"
bash scripts/cell_b/b10_release_rollback_rehearsal.sh
log "b10_release_rollback_script" "ok"

log "operator_status" "start"
WHITEPACT_ENV=development WHITEPACT_AUTH_ENABLED=false python -m responsibleai.operations.operator_status >/dev/null
log "operator_status" "ok"

python - <<PY
import json
from datetime import datetime, UTC
from pathlib import Path
out = Path("${ROOT}/artifacts/production/b12-zero-to-launch-summary.json")
out.write_text(json.dumps({
  "phase": "B12",
  "method": "SELF_REHEARSED",
  "source_sha": "$SHA",
  "finished_at": datetime.now(UTC).isoformat(),
  "log_artifact": "artifacts/production/b12-zero-to-launch.jsonl",
  "evidence_categories": ["INTEGRATION_TESTED", "REAL_POSTGRES_TESTED", "LOAD_TESTED", "RESTORE_TESTED"],
  "limitations": "No independent human operator; cluster deploy/rollback requires staging OWNER_ACTION_REQUIRED."
}, indent=2) + "\\n", encoding="utf-8")
PY
log "complete" "ok"
echo "B12 rehearsal complete. SHA=$SHA"
