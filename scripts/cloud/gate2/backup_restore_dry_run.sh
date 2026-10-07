#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# Encrypt and restore a fixture backup locally. Does not create an R2 bucket
# or call Cloudflare, Hetzner, or GCP.
set -euo pipefail

if [[ "${1:-}" == "--upload" ]]; then
  echo "GATE2_BACKUP=FAIL upload is not allowed in the dry run" >&2
  exit 1
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
install -m 0700 /dev/null "$WORK/key"
head -c 32 /dev/urandom > "$WORK/key"
printf '%s\n' '-- whitepact backup fixture' 'SELECT 1;' > "$WORK/plain.sql"
EXPECTED="$(sha256sum "$WORK/plain.sql" | awk '{print $1}')"
openssl enc -aes-256-cbc -pbkdf2 -salt -pass "file:$WORK/key" -in "$WORK/plain.sql" -out "$WORK/plain.sql.enc"
openssl enc -d -aes-256-cbc -pbkdf2 -pass "file:$WORK/key" -in "$WORK/plain.sql.enc" -out "$WORK/restored.sql"
ACTUAL="$(sha256sum "$WORK/restored.sql" | awk '{print $1}')"
if [[ "$ACTUAL" != "$EXPECTED" ]]; then
  echo "GATE2_BACKUP=FAIL digest mismatch" >&2
  exit 1
fi
if ! grep -q 'whitepact backup fixture' "$WORK/restored.sql"; then
  echo "GATE2_BACKUP=FAIL restored payload" >&2
  exit 1
fi
# Retention window used by the staging contract. A 31-day-old object fails.
python3 - "$EXPECTED" <<'PY'
import sys
from datetime import UTC, datetime, timedelta
retention_days = 30
fresh = datetime.now(UTC) - timedelta(days=1)
stale = datetime.now(UTC) - timedelta(days=31)
def keep(when):
    return datetime.now(UTC) - when <= timedelta(days=retention_days)
if not keep(fresh) or keep(stale):
    raise SystemExit("retention window check failed")
print("RESTORE_SHA256_MATCH=PASS")
print("RETENTION_DAYS_STAGING=30")
print("BACKUP_KEY_SCOPE=ephemeral-temp")
print("R2_UPLOAD=NO")
PY
echo "GATE2_BACKUP=PASS"
