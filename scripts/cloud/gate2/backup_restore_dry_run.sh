#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# Encrypt and decrypt a fixture dump with the production Fernet pipeline.
# Does not create an R2 bucket or call Cloudflare, Hetzner, or GCP.
set -euo pipefail

if [[ "${1:-}" == "--upload" ]]; then
  echo "GATE2_BACKUP=FAIL upload is not allowed in the dry run" >&2
  exit 1
fi

PYTHON="${WHITEPACT_PYTHON:-python3}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
chmod 700 "$WORK"
WHITEPACT_BACKUP_ENCRYPTION_KEY="$("$PYTHON" -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
export WHITEPACT_BACKUP_ENCRYPTION_KEY
printf '%s\n' '--' 'PostgreSQL database dump' '-- whitepact backup fixture' 'SELECT 1;' > "$WORK/plain.sql"
"$PYTHON" -m responsibleai.ops encrypt \
  --input "$WORK/plain.sql" \
  --output "$WORK/plain.sql.gz.enc" \
  --database fixture \
  --tool-version 1.3.1
"$PYTHON" -m responsibleai.ops prepare-restore \
  --backup "$WORK/plain.sql.gz.enc" \
  --work "$WORK/restored" >"$WORK/plan.json"
"$PYTHON" - "$WORK/plan.json" "$WORK/plain.sql" <<'PY'
import hashlib, json, sys
from pathlib import Path
plan = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
plain = Path(plan["plain_path"]).read_bytes()
expected = Path(sys.argv[2]).read_bytes()
if hashlib.sha256(plain).hexdigest() != hashlib.sha256(expected).hexdigest():
    raise SystemExit("digest mismatch")
if b"whitepact backup fixture" not in plain:
    raise SystemExit("restored payload")
if b"PostgreSQL database dump" not in plain:
    raise SystemExit("dump header")
print("RESTORE_SHA256_MATCH=PASS")
PY
"$PYTHON" - <<'PY'
from datetime import UTC, datetime, timedelta
from responsibleai.ops.r2_retention import BackupObject, plan_retention
now = datetime.now(UTC)
objects = [
    BackupObject("fresh", now - timedelta(days=1), True),
    BackupObject("boundary", now - timedelta(days=30), True),
    BackupObject("stale", now - timedelta(days=31), True),
    BackupObject("newest", now, True),
]
plan = plan_retention(objects, now=now, retain_days=30, min_recovery_points=2, destructive=False)
if "newest" in plan.delete or "fresh" in plan.delete or "boundary" in plan.delete:
    raise SystemExit("retention kept the wrong objects")
if "stale" not in plan.delete:
    raise SystemExit("retention window check failed")
if plan.dry_run is not True:
    raise SystemExit("retention must dry-run by default")
print("RETENTION_DAYS_STAGING=30")
print("BACKUP_KEY_SCOPE=ephemeral-temp")
print("R2_UPLOAD=NO")
PY
echo "GATE2_BACKUP=PASS"
