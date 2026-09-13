# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Canonical schema transitions: no implicit stamping or authority backfill."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from responsibleai.db.engine import create_engine
from responsibleai.db.migrate import (
    MigrationError,
    _find_alembic_ini,
    _migration_env,
    _run_alembic,
    run_migrations_or_raise,
)


def test_one_canonical_head():
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    assert scripts.get_heads() == ["0044"]
    assert scripts.get_revision("0044").down_revision == "0043"
    assert scripts.get_revision("0043").down_revision == "0042"
    assert scripts.get_revision("0033").down_revision == "0032"


@pytest.mark.parametrize("start", ["base", "0029", "0032"])
async def test_supported_upgrade_paths(tmp_path: Path, start: str):
    url = str(tmp_path / f"{start}.db")
    await _verify_upgrade(url, start)


async def _verify_upgrade(url: str, start: str):
    ini = _find_alembic_ini()
    assert ini is not None
    if start != "base":
        await _run_alembic(ini, _migration_env(url), "upgrade", start)
    await run_migrations_or_raise(url)
    await run_migrations_or_raise(url)
    engine = create_engine(url)
    try:
        async with engine.raw.connect() as conn:
            assert (
                await conn.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar() == "0044"
            tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
            assert {
                "oauth_clients",
                "web_users",
                "stripe_webhook_events",
                "governance_crypto_keys",
                "governance_consent_proofs",
                "governance_revocation_epochs",
                "governance_execution_nonces",
                "trust_fabric_principals",
                "trust_fabric_identifiers",
                "trust_fabric_trust_roots",
            } <= set(tables)
            fks = await conn.run_sync(
                lambda c: inspect(c).get_foreign_keys("governance_consent_proofs")
            )
            assert any(
                fk["referred_table"] == "governance_root_authority_records"
                and fk["constrained_columns"] == ["consenting_root_id", "organization_id"]
                for fk in fks
            )
        await _verify_tenant_constraints(engine)
    finally:
        await engine.close()


async def _verify_tenant_constraints(engine):
    from responsibleai.db.engine import (
        governance_consent_proofs,
        governance_root_authority_records,
        organizations,
    )

    async with engine.raw.connect() as conn:
        if conn.dialect.name == "sqlite":
            await conn.execute(text("PRAGMA foreign_keys=ON"))
            await conn.commit()
        # Roll back these fixtures: the migration test does not leave customer records.
        transaction = await conn.begin()
        try:
            await conn.execute(
                organizations.insert(),
                [
                    {"id": "tenant-a", "name": "A", "slug": "a", "created_at": "now"},
                    {"id": "tenant-b", "name": "B", "slug": "b", "created_at": "now"},
                ],
            )
            await conn.execute(
                governance_root_authority_records.insert().values(
                    root_id="root-a",
                    subject_id="person-a",
                    root_type="HUMAN",
                    organization_id="tenant-a",
                    issuer="customer",
                    verification_method="explicit",
                    evidence_refs="[]",
                    issued_at="now",
                    canonical_digest="a" * 64,
                )
            )
            proof = dict(
                consent_id="consent-a",
                organization_id="tenant-a",
                subject_id="person-a",
                consenting_root_id="root-a",
                grantee_id="machine-a",
                scope_description="none",
                purpose="support",
                consent_method="explicit",
                evidence_refs="[]",
                consented_at="now",
                canonical_digest="b" * 64,
            )
            await conn.execute(governance_consent_proofs.insert().values(**proof))
            row = (
                await conn.execute(
                    text(
                        "SELECT allowed_action_types, allowed_targets FROM governance_consent_proofs "
                        "WHERE consent_id='consent-a'"
                    )
                )
            ).one()
            assert tuple(row) == ("[]", "[]")
            nested = await conn.begin_nested()
            try:
                with pytest.raises(IntegrityError):
                    await conn.execute(
                        governance_consent_proofs.insert().values(
                            **{**proof, "consent_id": "cross-tenant", "organization_id": "tenant-b"}
                        )
                    )
            finally:
                await nested.rollback()
        finally:
            await transaction.rollback()


@pytest.mark.parametrize("problem", ["fork", "missing-tenant"])
async def test_evidence_preflight_preserves_conflicting_history(tmp_path, problem):
    url = str(tmp_path / "evidence.db")
    ini = _find_alembic_ini()
    assert ini is not None
    await _run_alembic(ini, _migration_env(url), "upgrade", "0035")
    engine = create_engine(url)
    try:
        async with engine.raw.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO organizations (id,name,slug,monthly_budget_usd,created_at) "
                    "VALUES ('a','A','a',0,'now')"
                )
            )
            for key in ("one", "two"):
                await conn.execute(
                    text(
                        "INSERT INTO governance_evidence "
                        "(id,org_id,action_id,agent_id,identity_id,action_type,target,"
                        "authority_delegated_by,decision,reason_codes,evaluated_at,recorded_at,entry_hash) "
                        "VALUES (:key,:org,:key,'agent','identity','read','target','owner','ALLOW','[]','now','now',:key)"
                    ),
                    {"key": key, "org": "a" if problem == "fork" else None},
                )
        with pytest.raises(MigrationError, match="fork|tenant ownership"):
            await run_migrations_or_raise(url)
        async with engine.raw.connect() as conn:
            assert (
                await conn.execute(text("SELECT count(*) FROM governance_evidence"))
            ).scalar() == 2
            assert (
                await conn.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar() == "0035"
    finally:
        await engine.close()


@pytest.mark.parametrize("start", ["base", "0029", "0032"])
async def test_postgres_upgrade_paths(start: str):
    """Each URL must name a disposable database; never reset caller data."""
    key = "WHITEPACT_TEST_POSTGRES_" + start.upper()
    url = os.environ.get(key)
    if not url:
        pytest.skip(f"{key} must name a fresh isolated test database")
    engine = create_engine(url)
    try:
        async with engine.raw.connect() as conn:
            assert not await conn.run_sync(lambda c: inspect(c).get_table_names()), (
                "Test DB must be empty"
            )
    finally:
        await engine.close()
    await _verify_upgrade(url, start)


async def test_unversioned_customer_data_is_not_stamped(tmp_path):
    url = str(tmp_path / "unversioned.db")
    engine = create_engine(url)
    async with engine.raw.begin() as conn:
        await conn.execute(text("CREATE TABLE customer_evidence (value TEXT)"))
        await conn.execute(text("INSERT INTO customer_evidence VALUES ('retain-me')"))
    with pytest.raises(MigrationError, match="unversioned"):
        await run_migrations_or_raise(url)
    async with engine.raw.connect() as conn:
        assert (
            await conn.execute(text("SELECT value FROM customer_evidence"))
        ).scalar() == "retain-me"
        assert "alembic_version" not in await conn.run_sync(lambda c: inspect(c).get_table_names())
    await engine.close()


async def test_legacy_revision_collision_is_rejected_without_stamp(tmp_path):
    url = str(tmp_path / "legacy.db")
    engine = create_engine(url)
    async with engine.raw.begin() as conn:
        await conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
        await conn.execute(text("INSERT INTO alembic_version VALUES ('0032')"))
        await conn.execute(text("CREATE TABLE governance_crypto_keys (key_id TEXT)"))
    with pytest.raises(MigrationError, match="legacy|canonical"):
        await run_migrations_or_raise(url)
    async with engine.raw.connect() as conn:
        assert (
            await conn.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar() == "0032"
    await engine.close()
