# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real PostgreSQL 16 and independent SQLite preflight; no READY publication."""

import json
import secrets
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from scripts.engineering.m13_bootstrap_authorization import BootstrapRefusedError
from scripts.engineering.m13_bootstrap_preflight import (
    collect_bootstrap_store_evidence,
    evidence_digest,
    verify_bootstrap_target_binding,
)
from sqlalchemy import text

from responsibleai.data_governance.backup_defense import (
    RestoreReadinessState,
    SqliteDurableLifecycleStateProvider,
)
from responsibleai.data_governance.tenant_controller import postgres_identity, store_b_identity
from responsibleai.db.engine import create_engine
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.db.web_identity_repository import WebIdentityRepository
from tests.pg_test_url import isolated_pg_url


@pytest.fixture
async def fresh_target(tmp_path, monkeypatch):
    monkeypatch.setenv("WHITEPACT_ENV", "staging")
    async for url in isolated_pg_url("wp_bootstrap_preflight"):
        await _run_alembic(_find_alembic_ini(), _migration_env(url), "upgrade", "0067")
        engine = create_engine(url)
        try:
            provider = SqliteDurableLifecycleStateProvider(
                tmp_path / "b.sqlite3", secret_key=secrets.token_hex(32)
            )
            async with engine.raw.connect() as connection:
                pg = await postgres_identity(connection)
            config = {
                "purpose": "NONPRODUCTION_BOOTSTRAP_QUALIFICATION",
                "installation_id": secrets.token_hex(32),
                "deployment_id": "bootstrap-preflight-fixture",
                "environment": "staging",
                "postgres_identity": pg,
                "store_b_identity": store_b_identity(provider),
                "registry": str(tmp_path / "external.sqlite3"),
                "operators": {
                    role: {
                        "identity": role.lower(),
                        "public_key": Ed25519PrivateKey.generate()
                        .public_key()
                        .public_bytes_raw()
                        .hex(),
                        "revoked": False,
                    }
                    for role in ("SECURITY_OWNER", "DEPLOYMENT_OPERATOR")
                },
            }
            profile = tmp_path / "private.json"
            profile.write_text(json.dumps(config))
            profile.chmod(0o600)
            yield engine, provider, profile, config
        finally:
            await engine.close()


@pytest.mark.asyncio
async def test_real_fresh_stores_have_stable_evidence_but_no_bootstrap_authority(fresh_target):
    engine, provider, profile, config = fresh_target
    first = await collect_bootstrap_store_evidence(engine, provider, profile_path=profile)
    await engine.raw.dispose()
    second = await collect_bootstrap_store_evidence(engine, provider, profile_path=profile)
    assert first == second and evidence_digest(first) == evidence_digest(second)
    assert first["ready"] is False and provider.get_readiness_state() is None
    assert not any(first["postgres_table_counts"].values())
    assert not any(first["store_b_table_counts"].values())
    from pathlib import Path

    assert not Path(config["registry"]).exists()


@pytest.mark.asyncio
async def test_proposed_manifest_must_match_actual_target_evidence(fresh_target):
    """Read-only target binding is necessary, not signature or admission proof."""
    from dataclasses import replace

    from scripts.engineering.m13_bootstrap_authorization import BootstrapManifest

    engine, provider, profile, config = fresh_target
    evidence = await collect_bootstrap_store_evidence(engine, provider, profile_path=profile)
    now = int(time.time())
    manifest = BootstrapManifest(
        installation_id=config["installation_id"],
        deployment_id=config["deployment_id"],
        environment=config["environment"],
        postgres_identity=config["postgres_identity"],
        store_b_identity=config["store_b_identity"],
        evidence_digest=evidence_digest(evidence),
        nonce=secrets.token_hex(32),
        created_at=now,
        expires_at=now + 120,
    )
    actual = await verify_bootstrap_target_binding(
        engine, provider, profile_path=profile, manifest=manifest
    )
    assert actual == evidence
    with pytest.raises(BootstrapRefusedError, match="evidence digest"):
        await verify_bootstrap_target_binding(
            engine,
            provider,
            profile_path=profile,
            manifest=replace(manifest, evidence_digest="0" * 64),
        )
    with pytest.raises(BootstrapRefusedError, match="target binding"):
        await verify_bootstrap_target_binding(
            engine,
            provider,
            profile_path=profile,
            manifest=replace(manifest, deployment_id="another-deployment"),
        )
    await WebIdentityRepository(engine).register(
        "Changed target", "changed@example.test", "Test-Only-Password-42!"
    )
    with pytest.raises(BootstrapRefusedError, match="Existing Store A history"):
        await verify_bootstrap_target_binding(
            engine, provider, profile_path=profile, manifest=manifest
        )
    assert provider.get_readiness_state() is None
    from pathlib import Path

    assert not Path(config["registry"]).exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "history",
    [
        "identity",
        "restrictive-readiness",
        "wrong-postgres",
        "wrong-store-b",
        "missing-authority-table",
    ],
)
async def test_used_or_mismatched_target_never_becomes_bootstrap_ready(fresh_target, history):
    engine, provider, profile, config = fresh_target
    if history == "identity":
        await WebIdentityRepository(engine).register(
            "Prior user", "prior@example.test", "Test-Only-Password-42!"
        )
    elif history == "restrictive-readiness":
        provider.set_readiness_state(RestoreReadinessState.RESTORE_PENDING)
    elif history == "missing-authority-table":
        async with engine.raw.begin() as connection:
            await connection.execute(text("DROP TABLE governance_execution_nonces"))
    else:
        field = "postgres_identity" if history == "wrong-postgres" else "store_b_identity"
        config[field] = "0" * 64
        profile.write_text(json.dumps(config))
    with pytest.raises(BootstrapRefusedError):
        await collect_bootstrap_store_evidence(engine, provider, profile_path=profile)
    assert provider.get_readiness_state() != RestoreReadinessState.READY
    from pathlib import Path

    assert not Path(config["registry"]).exists()
