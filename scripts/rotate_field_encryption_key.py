#!/usr/bin/env python3
"""Re-encrypt every field-encrypted column under the current *first* key in
RAI_FIELD_ENCRYPTION_KEY, so the old key(s) after it can be safely dropped.

Read compliance/KEY_MANAGEMENT.md before running this — it explains the
full rotation procedure this script is one step of. In short:

    1. Generate a new Fernet key.
    2. Put it FIRST in RAI_FIELD_ENCRYPTION_KEY (comma-separated), keeping
       the old key(s) after it so existing ciphertext still decrypts.
    3. Restart the app (or just set the env var for this script's own run).
    4. Run this script — it reads every row of every encrypted column
       through the ORM (which decrypts with whichever key in the list
       matches) and writes it back (which always encrypts with the first
       key), one table transaction at a time.
    5. Only once this has completed successfully against your real
       database should you drop the old key from RAI_FIELD_ENCRYPTION_KEY
       and restart again.

Safe to re-run: rows already encrypted under the current first key are
read and rewritten as a no-op (same ciphertext-producing plaintext).

Usage:
    RAI_FIELD_ENCRYPTION_KEY="new_key,old_key" RAI_DB_PATH=./data/rai.db \
        python scripts/rotate_field_encryption_key.py

    # or against Postgres:
    RAI_FIELD_ENCRYPTION_KEY="new_key,old_key" \
        RAI_DATABASE_URL=postgresql+asyncpg://... \
        python scripts/rotate_field_encryption_key.py
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlalchemy import select, update  # noqa: E402

from responsibleai.db.encryption import _load_fernet  # noqa: E402
from responsibleai.db.engine import (  # noqa: E402
    audit_log,
    create_engine,
    org_api_keys,
    public_incident_reports,
    webhook_configs,
)

# (table, [encrypted columns]) — kept in sync with db/engine.py's EncryptedString usage.
_ENCRYPTED_COLUMNS = [
    (audit_log, ["ip_address"]),
    (public_incident_reports, ["reporter_name", "reporter_contact"]),
    (webhook_configs, ["secret"]),
    (org_api_keys, ["mfa_secret"]),
]


async def _rotate_table(conn, table, columns: list[str]) -> int:
    id_col = table.c.id
    cols = [id_col, *(table.c[c] for c in columns)]
    result = await conn.execute(select(*cols))
    rows = result.fetchall()

    rewritten = 0
    for row in rows:
        row_id = row[0]
        values = dict(zip(columns, row[1:], strict=True))
        if all(v is None for v in values.values()):
            continue
        # SELECT already ran each value through EncryptedString.process_result_value
        # (decrypt with whichever key matches) via the ORM type engine; writing
        # it back runs process_bind_param (encrypt with the current first key).
        await conn.execute(update(table).where(id_col == row_id).values(**values))
        rewritten += 1
    return rewritten


async def main() -> None:
    if _load_fernet() is None:
        print(
            "RAI_FIELD_ENCRYPTION_KEY is not set — nothing to rotate. "
            "Set it to 'new_key,old_key' before running this script.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    db_url = os.environ.get("RAI_DATABASE_URL") or os.environ.get("RAI_DB_PATH", "./data/rai.db")
    engine = create_engine(db_url)
    total = 0
    try:
        async with engine.raw.begin() as conn:
            for table, columns in _ENCRYPTED_COLUMNS:
                count = await _rotate_table(conn, table, columns)
                print(f"  {table.name}: re-encrypted {count} row(s) across {columns}")
                total += count
    finally:
        await engine.close()

    print(f"Done — {total} row(s) re-encrypted under the current first key.")
    print("Verify against your real data, then drop the old key from")
    print("RAI_FIELD_ENCRYPTION_KEY and restart once you're confident.")


if __name__ == "__main__":
    asyncio.run(main())
