# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Disposable PostgreSQL proof of version-scoped credential retirement.

No production credential is read or changed. This qualifies an operations
contract, not a retroactive code fix or a historical-binary execution receipt.
"""

import secrets
import uuid
from contextlib import aclosing

import asyncpg
import pytest

from tests.pg_test_url import isolated_pg_url


def quoted(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


@pytest.mark.asyncio
async def test_version_credentials_fence_new_and_already_open_legacy_connections():
    async with aclosing(isolated_pg_url("wp_role_retirement")) as databases:
        async for database in databases:
            admin = await asyncpg.connect(database)
            old_role = "wp_old_" + uuid.uuid4().hex
            new_role = "wp_new_" + uuid.uuid4().hex
            password = secrets.token_hex(24)
            created = []
            old = current = None
            try:
                db_name = quoted(await admin.fetchval("SELECT current_database()"))
                for role in (old_role, new_role):
                    # Fixed generated identifier and hex-only ephemeral password;
                    # utility statements cannot bind these SQL grammar positions.
                    await admin.execute(f"CREATE ROLE {quoted(role)} LOGIN PASSWORD '{password}'")
                    created.append(role)
                await admin.execute(f"REVOKE CONNECT ON DATABASE {db_name} FROM PUBLIC")
                for role in created:
                    await admin.execute(f"GRANT CONNECT ON DATABASE {db_name} TO {quoted(role)}")
                    await admin.execute(f"GRANT USAGE ON SCHEMA public TO {quoted(role)}")
                await admin.execute("CREATE TABLE compatibility_effects (value text NOT NULL)")
                await admin.execute(
                    f"GRANT SELECT, INSERT ON compatibility_effects TO {quoted(old_role)}, {quoted(new_role)}"
                )
                old = await asyncpg.connect(database, user=old_role, password=password)
                current = await asyncpg.connect(database, user=new_role, password=password)
                await old.execute(
                    "INSERT INTO compatibility_effects VALUES ('legacy-before-fence')"
                )
                await old.execute("BEGIN")
                await old.execute("INSERT INTO compatibility_effects VALUES ('uncommitted-legacy')")

                # Negative control: CONNECT revocation alone does not fence an
                # existing pool connection and must never be sold as sufficient.
                await admin.execute(f"REVOKE CONNECT ON DATABASE {db_name} FROM {quoted(old_role)}")
                assert await old.fetchval("SELECT 1") == 1
                await old.execute(
                    "INSERT INTO compatibility_effects VALUES ('legacy-after-revoke')"
                )

                # Retirement is an explicit operator action, not app startup code.
                await admin.execute(f"ALTER ROLE {quoted(old_role)} NOLOGIN")
                terminated = await admin.fetch(
                    "SELECT pg_terminate_backend(pid, 5000) AS terminated "
                    "FROM pg_stat_activity WHERE datname=current_database() AND usename=$1",
                    old_role,
                )
                assert terminated and all(row["terminated"] for row in terminated)
                with pytest.raises((asyncpg.PostgresConnectionError, asyncpg.InterfaceError)):
                    await old.fetchval("SELECT 1")
                with pytest.raises(asyncpg.InvalidAuthorizationSpecificationError):
                    await asyncpg.connect(database, user=old_role, password=password)
                assert (
                    await admin.fetchval(
                        "SELECT count(*) FROM compatibility_effects WHERE value='uncommitted-legacy'"
                    )
                    == 0
                )
                assert (
                    await admin.fetchval(
                        "SELECT count(*) FROM compatibility_effects WHERE value='legacy-after-revoke'"
                    )
                    == 0
                )

                # Current runtime stays operational, cannot assume the legacy role,
                # and reconnects successfully after its own connection is closed.
                await current.execute(
                    "INSERT INTO compatibility_effects VALUES ('current-after-fence')"
                )
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await current.execute(f"SET ROLE {quoted(old_role)}")
                await current.close()
                current = await asyncpg.connect(database, user=new_role, password=password)
                assert await current.fetchval("SELECT count(*) FROM compatibility_effects") == 2

                # Recovery must not accidentally resurrect a retired login even
                # when a database restore/regrant restores PUBLIC CONNECT.
                await admin.execute(f"GRANT CONNECT ON DATABASE {db_name} TO PUBLIC")
                with pytest.raises(asyncpg.InvalidAuthorizationSpecificationError):
                    await asyncpg.connect(database, user=old_role, password=password)
            finally:
                for connection in (old, current):
                    if connection is not None:
                        await connection.close()
                for role in reversed(created):
                    await admin.execute(f"DROP OWNED BY {quoted(role)}")
                    await admin.execute(f"DROP ROLE {quoted(role)}")
                await admin.close()
