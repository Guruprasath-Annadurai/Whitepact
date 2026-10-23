# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Explicit application/schema startup contract, including out-of-band migrations."""

from sqlalchemy import text

from responsibleai.db.engine import DatabaseEngine

# Review this alongside every security-bearing migration. Do not silently accept
# newer schema semantics merely because existing ORM queries still work.
# This runtime requires 0067's protected tenant provisioning projection as well
# as 0066's containment journal and 0065's mandatory passkeys. Older and newer
# revisions are not implicitly compatible; partial/multiple heads also fail.
SUPPORTED_POSTGRES_REVISIONS = frozenset({"0067"})


async def assert_runtime_schema_compatible(engine: DatabaseEngine) -> None:
    if engine.raw.dialect.name != "postgresql":
        return
    try:
        async with engine.raw.connect() as connection:
            versions = frozenset(
                (await connection.execute(text("SELECT version_num FROM alembic_version")))
                .scalars()
                .all()
            )
    except Exception as exc:
        raise RuntimeError(
            "Startup refused: PostgreSQL schema compatibility is unverified"
        ) from exc
    if versions != SUPPORTED_POSTGRES_REVISIONS:
        raise RuntimeError("Startup refused: incompatible PostgreSQL schema revision")
