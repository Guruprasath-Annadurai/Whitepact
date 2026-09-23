#!/usr/bin/env bash
# Non-production SQLite restore drill for DR evidence (not production Postgres proof).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
ART="$ROOT/compliance/csa-star-ai/evidence/dr"
mkdir -p "$ART"
DB="$ART/drill.db"
BAK="$ART/drill-$(date -u +%Y%m%dT%H%M%SZ).sql"
LOG="$ART/last_drill.log"
START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
rm -f "$DB"
export PYTHONPATH="$ROOT/src"
python - <<'PY'
import asyncio
from pathlib import Path
from responsibleai.db.engine import create_engine

async def seed():
    eng = create_engine(str(Path("compliance/csa-star-ai/evidence/dr/drill.db").resolve()))
    await eng.init()
    async with eng.raw.begin() as conn:
        await conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS dr_marker (id INTEGER PRIMARY KEY, note TEXT)"
        )
        await conn.exec_driver_sql(
            "INSERT INTO dr_marker (note) VALUES ('pre-backup')"
        )
    await eng.close()

asyncio.run(seed())
PY
sqlite3 "$DB" .dump > "$BAK"
rm -f "$DB"
sqlite3 "$DB" < "$BAK"
NOTE=$(sqlite3 "$DB" "SELECT note FROM dr_marker LIMIT 1;")
END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
{
  echo "backup_file=$BAK"
  echo "restore_start=$START"
  echo "restore_end=$END"
  echo "integrity_note=$NOTE"
  echo "result=$([ "$NOTE" = "pre-backup" ] && echo PASS || echo FAIL)"
} | tee "$LOG"
test "$NOTE" = "pre-backup"
