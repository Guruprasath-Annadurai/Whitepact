#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# Print Gate 2 signal evaluation as JSON. This does not send an alert.
set -euo pipefail
PYTHON="${WHITEPACT_PYTHON:-python3}"
exec "$PYTHON" - <<'PY'
import json
import os
from responsibleai.ops.gate2_signals import SignalSnapshot, evaluate

def optional_float(name: str) -> float | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    return float(raw)

def optional_bool(name: str) -> bool | None:
    raw = os.environ.get(name, "").strip().lower()
    if raw in {"1", "true", "yes"}:
        return True
    if raw in {"0", "false", "no"}:
        return False
    return None

snapshot = SignalSnapshot(
    backup_age_hours=optional_float("WHITEPACT_SIGNAL_BACKUP_AGE_HOURS"),
    backup_failed=os.environ.get("WHITEPACT_SIGNAL_BACKUP_FAILED", "").strip().lower() in {"1", "true", "yes"},
    restore_drill_failed=os.environ.get("WHITEPACT_SIGNAL_RESTORE_DRILL_FAILED", "").strip().lower() in {"1", "true", "yes"},
    origin_tls_failed=os.environ.get("WHITEPACT_SIGNAL_ORIGIN_TLS_FAILED", "").strip().lower() in {"1", "true", "yes"},
    disk_used_percent=optional_float("WHITEPACT_SIGNAL_DISK_USED_PERCENT"),
    db_connected=optional_bool("WHITEPACT_SIGNAL_DB_CONNECTED"),
    application_healthy=optional_bool("WHITEPACT_SIGNAL_APPLICATION_HEALTHY"),
    execution_healthy=optional_bool("WHITEPACT_SIGNAL_EXECUTION_HEALTHY"),
)
print(json.dumps({"alerts_dispatched": False, "signals": evaluate(snapshot)}, sort_keys=True))
PY
