#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Independent schema/data probe; fixture rows never qualify customer authority."""

from __future__ import annotations

import argparse
import asyncio
import json
from contextlib import aclosing
from pathlib import Path

import asyncpg
from scripts.engineering.m13i3_browser_journey import git_identity
from tests.pg_test_url import isolated_pg_url

from responsibleai.db.migrate import _migration_env, _run_alembic


async def qualify(implementation: Path) -> dict:
    ini = implementation.resolve() / "alembic.ini"
    assert ini.is_file()
    result = {"implementation": git_identity(implementation), "customer_authority": False}
    async with aclosing(isolated_pg_url("wp_apex_preservation")) as databases:
        async for url in databases:
            env = _migration_env(url)

            async def migrate(*args, migration_env=env):
                await _run_alembic(ini, migration_env, *args)

            await migrate("upgrade", "0063")
            await migrate("upgrade", "0064")
            connection = await asyncpg.connect(url)
            try:
                result["postgres_version"] = await connection.fetchval("SHOW server_version")
                for index in range(2):
                    org = f"apex-schema-{index}"
                    await connection.execute(
                        "INSERT INTO organizations(id,name,slug,created_at) VALUES($1,$1,$1,'2026-01-01')",
                        org,
                    )
                    await connection.execute(
                        "INSERT INTO trust_fabric_bootstrap_records"
                        "(id,org_id,token_hash,expires_at,nonce,created_at)"
                        " VALUES($1,$1,$2,'2020-01-01',$1,'2020-01-01')",
                        org,
                        "0" * 64,
                    )
                    await connection.execute(
                        "INSERT INTO authority_recovery_requests"
                        "(id,org_id,request_type,requester_user_id,proposed_parameters_json,"
                        "action_digest,created_at,expires_at)"
                        " VALUES($1,$1,'SCHEMA_FIXTURE','fixture','{}','digest','2020-01-01','2020-01-01')",
                        org,
                    )

                async def snapshot(connection=connection):
                    tables = (
                        "organizations",
                        "trust_fabric_bootstrap_records",
                        "authority_recovery_requests",
                    )
                    return {
                        table: [
                            {
                                key: value
                                for key, value in dict(row).items()
                                if key != "require_passkey_stepup"
                            }
                            for row in await connection.fetch(f"SELECT * FROM {table} ORDER BY id")
                        ]
                        for table in tables
                    }

                before = await snapshot()
                await migrate("upgrade", "head")
                assert (
                    await connection.fetchval("SELECT version_num FROM alembic_version") == "0065"
                )
                assert await snapshot() == before
                defaults = await connection.fetch(
                    "SELECT require_passkey_stepup FROM trust_fabric_bootstrap_records"
                )
                assert len(defaults) == 2 and all(row[0] == 0 for row in defaults)
                column = await connection.fetchrow(
                    "SELECT is_nullable,column_default FROM information_schema.columns"
                    " WHERE table_name='trust_fabric_bootstrap_records' AND column_name='require_passkey_stepup'"
                )
                assert column["is_nullable"] == "NO" and column["column_default"] is not None
                result["upgrade"] = {
                    "status": "PASS",
                    "sequence": ["0063", "0064", "0065"],
                    "tenants": 2,
                    "existing_rows_preserved": True,
                    "non_null_defaults": True,
                }
                await connection.execute(
                    "UPDATE trust_fabric_bootstrap_records SET require_passkey_stepup=1"
                )
                await migrate("downgrade", "0064")
                assert await snapshot() == before
                await migrate("upgrade", "head")
                restored = await connection.fetch(
                    "SELECT require_passkey_stepup FROM trust_fabric_bootstrap_records"
                )
                retained = all(row[0] == 1 for row in restored)
                result["downgrade_roundtrip"] = {
                    "status": "PASS" if retained else "BLOCKED",
                    "ordinary_rows_preserved": True,
                    "security_flag_preserved": retained,
                    "reason": None
                    if retained
                    else "0065_DOWNGRADE_DROPS_PASSKEY_REQUIREMENT; DO_NOT_QUALIFY_NONEMPTY_DOWNGRADE",
                }
            finally:
                await connection.close()
    result["production"] = "GLOBAL PRODUCTION NO-GO"
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--implementation", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = asyncio.run(qualify(args.implementation))
    except Exception as error:
        receipt = {"status": "FAIL", "error_type": type(error).__name__}
    args.report.write_text(json.dumps(receipt, indent=2) + "\n")
    raise SystemExit(0 if receipt.get("downgrade_roundtrip", {}).get("status") == "PASS" else 2)
