# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Provider-session uniqueness at the accepted PostgreSQL revision.

Revision 0068 is not an accepted runtime or bootstrap schema. Signed
bootstrap evidence and the tenant controller still require exactly 0067.
This module installs the unique index on a database that is already at
0067. It does not stamp a new revision, delete rows, or accept 0068.
"""

from __future__ import annotations

from sqlalchemy import text

from responsibleai.db.engine import DatabaseEngine

IDENTITY_SESSION_INDEX = "uq_identity_verification_provider_session"


class IdentitySessionConflictError(RuntimeError):
    """Conflicting provider sessions exist. Nothing was deleted or merged."""


async def ensure_identity_session_uniqueness(engine: DatabaseEngine) -> None:
    """Create the unique session index when the accepted revision is 0067.

    A database at any other revision is left unchanged. Duplicate
    ``(provider, provider_reference_id)`` rows abort the index build and
    remain stored for review.
    """
    if engine.raw.dialect.name != "postgresql":
        return
    async with engine.raw.begin() as connection:
        versions = (
            (await connection.execute(text("SELECT version_num FROM alembic_version")))
            .scalars()
            .all()
        )
        if versions != ["0067"]:
            return
        present = await connection.scalar(
            text("SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :name"),
            {"name": IDENTITY_SESSION_INDEX},
        )
        if present:
            return
        conflicts = (
            await connection.execute(
                text(
                    """
                    SELECT provider, provider_reference_id, count(*)
                    FROM identity_verifications
                    WHERE provider_reference_id IS NOT NULL
                    GROUP BY provider, provider_reference_id
                    HAVING count(*) > 1
                    """
                )
            )
        ).fetchall()
        if conflicts:
            raise IdentitySessionConflictError(
                "Refusing to build the identity session unique index. "
                "Conflicting provider sessions were left unchanged."
            )
        await connection.execute(
            text(
                f"CREATE UNIQUE INDEX {IDENTITY_SESSION_INDEX} "
                "ON identity_verifications (provider, provider_reference_id)"
            )
        )
