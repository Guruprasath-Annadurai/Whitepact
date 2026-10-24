# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Read-only, nonproduction Store A/B bootstrap evidence collection.

This is NOT a complete bootstrap controller. It cannot publish READY, establish
host/operator identity, attest external installation history or authorize traffic.
Workload verification, independently protected completion and runtime binding are
mandatory separate prerequisites before any future publisher may be implemented.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from scripts.engineering.m13_bootstrap_authorization import (
    BootstrapManifest,
    BootstrapRefusedError,
    _profile,
)
from sqlalchemy import text

from responsibleai.data_governance.backup_defense import SqliteDurableLifecycleStateProvider
from responsibleai.data_governance.tenant_controller import postgres_identity, store_b_identity
from responsibleai.db.engine import DatabaseEngine

FORMAT = "WHITEPACT-M13-BOOTSTRAP-STORE-PREFLIGHT-V1"


async def verify_bootstrap_target_binding(
    engine: DatabaseEngine,
    provider: SqliteDurableLifecycleStateProvider,
    *,
    profile_path: str | Path,
    manifest: BootstrapManifest,
) -> dict[str, Any]:
    """Bind a proposed manifest to actual stores; NOT signature or admission proof.

    This read-only check cannot consume approval or publish readiness. A future
    publisher must independently verify signatures and repeat freshness checks
    under exclusive operation/store locks before any mutation.
    """
    if type(manifest) is not BootstrapManifest:
        raise BootstrapRefusedError("Exact bootstrap manifest required")
    manifest.canonical_bytes()
    profile = _profile(profile_path)
    for field in (
        "installation_id",
        "deployment_id",
        "environment",
        "postgres_identity",
        "store_b_identity",
    ):
        if getattr(manifest, field) != profile[field]:
            raise BootstrapRefusedError("Bootstrap target binding mismatch")
    evidence = await collect_bootstrap_store_evidence(engine, provider, profile_path=profile_path)
    if manifest.evidence_digest != evidence_digest(evidence):
        raise BootstrapRefusedError("Bootstrap evidence digest mismatch")
    return evidence


def evidence_digest(evidence: dict[str, Any]) -> str:
    if type(evidence) is not dict or evidence.get("format") != FORMAT:
        raise BootstrapRefusedError("Unsupported bootstrap store evidence")
    return hashlib.sha256(
        json.dumps(evidence, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
    ).hexdigest()


async def collect_bootstrap_store_evidence(
    engine: DatabaseEngine,
    provider: SqliteDurableLifecycleStateProvider,
    *,
    profile_path: str | Path,
) -> dict[str, Any]:
    """Read the actual exact targets; absence is evidence, never authorization.

    Intentionally refuses every nonempty application table, including identity
    history. No migration reference-data exceptions or inferred newness exist.
    The caller must revalidate freshness under locks before any future mutation.
    """
    profile = _profile(profile_path)
    if (
        engine.raw.dialect.name != "postgresql"
        or engine.raw.url.host not in {None, "localhost", "127.0.0.1", "::1"}
        or type(provider) is not SqliteDurableLifecycleStateProvider
        or not provider._secret_key
    ):
        raise BootstrapRefusedError(
            "Exact local PostgreSQL and authenticated durable Store B required"
        )
    if store_b_identity(provider) != profile["store_b_identity"] or not provider.verify_integrity():
        raise BootstrapRefusedError("Store B target or integrity mismatch")
    async with engine.raw.connect() as connection, connection.begin():
        await connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        version = int(await connection.scalar(text("SHOW server_version_num")))
        revisions = (
            (await connection.execute(text("SELECT version_num FROM alembic_version")))
            .scalars()
            .all()
        )
        if not 160000 <= version < 170000 or revisions != ["0067"]:
            raise BootstrapRefusedError("Bootstrap requires PostgreSQL 16 and exactly schema 0067")
        pg_identity = await postgres_identity(connection)
        if pg_identity != profile["postgres_identity"]:
            raise BootstrapRefusedError("PostgreSQL target mismatch")
        names = (
            (
                await connection.execute(
                    text(
                        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
                    )
                )
            )
            .scalars()
            .all()
        )
        from responsibleai.data_governance.operator_recovery_control import _TABLES

        if not (set(_TABLES) | {"web_users"}).issubset(names):
            raise BootstrapRefusedError(
                "Missing authority tables cannot prove an unused deployment"
            )
        counts = {}
        for name in names:
            if name == "alembic_version":
                continue
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is None:
                raise BootstrapRefusedError("Unexpected application table identifier")
            counts[name] = int(
                await connection.scalar(text(f'SELECT count(*) FROM public."{name}"'))
            )
        if any(counts.values()):
            raise BootstrapRefusedError(
                "Existing Store A history forbids first-deployment bootstrap"
            )
    store_b_connection = provider._get_connection()
    try:
        store_b_connection.execute("BEGIN")
        names = [
            row[0]
            for row in store_b_connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        if not {"durable_tenant_lifecycle_states", "durable_restore_readiness"}.issubset(names):
            raise BootstrapRefusedError("Missing durable tables cannot prove an unused Store B")
        b_counts = {}
        for name in names:
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is None:
                raise BootstrapRefusedError("Unexpected durable table identifier")
            b_counts[name] = store_b_connection.execute(
                f'SELECT count(*) FROM "{name}"'
            ).fetchone()[0]
        if any(b_counts.values()):
            raise BootstrapRefusedError(
                "Existing Store B history forbids first-deployment bootstrap"
            )
    finally:
        store_b_connection.close()
    return {
        "format": FORMAT,
        "installation_id": profile["installation_id"],
        "deployment_id": profile["deployment_id"],
        "environment": profile["environment"],
        "postgres_identity": pg_identity,
        "schema_revision": "0067",
        "store_b_identity": profile["store_b_identity"],
        "postgres_table_counts": counts,
        "store_b_table_counts": b_counts,
        "read_only": True,
        "ready": False,
    }
