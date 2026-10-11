#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# Plan R2 backup retention. Dry-run unless --delete is passed.
# --delete still refuses the newest viable recovery points.
set -euo pipefail

DELETE=0
if [ "${1:-}" = "--delete" ]; then
  DELETE=1
  shift
fi
PLAN_FILE="${1:?usage: enforce_r2_retention.sh [--delete] plan.json}"
PYTHON="${WHITEPACT_PYTHON:-python3}"
WHITEPACT_R2_RETENTION_DELETE="$DELETE" "$PYTHON" - "$PLAN_FILE" <<'PY'
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from responsibleai.ops.r2_retention import BackupObject, plan_retention

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
now = datetime.fromisoformat(payload["now"])
objects = [
    BackupObject(item["key"], datetime.fromisoformat(item["created_at"]), item.get("viable", True))
    for item in payload["objects"]
]
destructive = os.environ.get("WHITEPACT_R2_RETENTION_DELETE") == "1"
plan = plan_retention(
    objects,
    now=now,
    retain_days=int(payload.get("retain_days", 30)),
    min_recovery_points=int(payload.get("min_recovery_points", 3)),
    tz_name=payload.get("tz", "UTC"),
    destructive=destructive,
)
print(json.dumps({"dry_run": plan.dry_run, "delete": list(plan.delete), "keep": list(plan.keep)}))
PY
