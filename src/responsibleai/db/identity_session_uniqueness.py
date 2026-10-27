# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Provider-session uniqueness at the accepted PostgreSQL revision.

Revision 0068 is not an accepted runtime or bootstrap schema. Signed
bootstrap evidence and the tenant controller still require exactly 0067.
This module installs the unique index on a database that is already at
0067. It does not stamp a new revision, delete rows, or accept 0068.

A same-named index is not enough. Startup accepts the name only when the
PostgreSQL catalog shows an immediate, valid, ready unique index on
``identity_verifications (provider, provider_reference_id)`` with no
predicate and no expression. Any other index with that name is left in
place and startup fails closed.
"""

from __future__ import annotations

from sqlalchemy import text

from responsibleai.db.engine import DatabaseEngine

IDENTITY_SESSION_INDEX = "uq_identity_verification_provider_session"
_SESSION_KEY = ("provider", "provider_reference_id")


class IdentitySessionConflictError(RuntimeError):
    """Conflicting provider sessions exist. Nothing was deleted or merged."""


class IdentitySessionIndexInvalidError(RuntimeError):
    """The named index does not enforce provider-session uniqueness."""


_INDEX_CATALOG = text(
    """
    SELECT
        n.nspname AS table_schema,
        c.relname AS table_name,
        i.indisunique,
        i.indisprimary,
        i.indisexclusion,
        i.indimmediate,
        i.indisvalid,
        i.indisready,
        i.indislive,
        i.indpred IS NULL AS no_predicate,
        i.indexprs IS NULL AS no_expression,
        i.indnkeyatts,
        (
            SELECT array_agg(a.attname ORDER BY k.ord)
            FROM unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord)
            JOIN pg_attribute a
              ON a.attrelid = i.indrelid AND a.attnum = k.attnum
            WHERE k.ord <= i.indnkeyatts AND k.attnum > 0
        ) AS key_columns,
        cardinality(i.indkey) AS key_count
    FROM pg_class idx
    JOIN pg_namespace ns ON ns.oid = idx.relnamespace
    JOIN pg_index i ON i.indexrelid = idx.oid
    JOIN pg_class c ON c.oid = i.indrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE ns.nspname = 'public' AND idx.relname = :name
    """
)


def _enforces_session_uniqueness(row) -> bool:
    keys = tuple(row["key_columns"] or ())
    return (
        row["table_schema"] == "public"
        and row["table_name"] == "identity_verifications"
        and row["indisunique"] is True
        and row["indisprimary"] is False
        and row["indisexclusion"] is False
        and row["indimmediate"] is True
        and row["indisvalid"] is True
        and row["indisready"] is True
        and row["indislive"] is True
        and row["no_predicate"] is True
        and row["no_expression"] is True
        and row["indnkeyatts"] == 2
        and row["key_count"] == 2
        and keys == _SESSION_KEY
    )


async def ensure_identity_session_uniqueness(engine: DatabaseEngine) -> None:
    """Create the unique session index when the accepted revision is 0067.

    A database at any other revision is left unchanged. Duplicate
    ``(provider, provider_reference_id)`` rows abort the index build and
    remain stored for review. An existing index with this name is not
    dropped or replaced when its catalog definition is wrong.
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
        row = (
            (await connection.execute(_INDEX_CATALOG, {"name": IDENTITY_SESSION_INDEX}))
            .mappings()
            .first()
        )
        if row is not None:
            if _enforces_session_uniqueness(row):
                return
            raise IdentitySessionIndexInvalidError(
                "Refusing startup. The identity session index name exists but "
                "does not enforce provider and provider_reference_id uniqueness. "
                "The index and stored identity rows were left unchanged."
            )
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
        created = (
            (await connection.execute(_INDEX_CATALOG, {"name": IDENTITY_SESSION_INDEX}))
            .mappings()
            .one()
        )
        if not _enforces_session_uniqueness(created):
            raise IdentitySessionIndexInvalidError(
                "Refusing startup. The identity session index did not meet "
                "the catalog uniqueness guarantee. The build was rolled back."
            )
