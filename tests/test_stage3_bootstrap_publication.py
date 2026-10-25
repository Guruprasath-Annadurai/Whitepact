# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Actual isolated PG16/durable SQLite/Docker bootstrap, never production keys."""

import base64
import json
import multiprocessing
import os
import re
import secrets
import sqlite3
import subprocess
import time
from dataclasses import replace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from scripts.engineering.m13_bootstrap_authorization import (
    BootstrapManifest,
    BootstrapRefusedError,
    register_signed_new_installation,
)
from scripts.engineering.m13_bootstrap_preflight import (
    collect_bootstrap_store_evidence,
)
from scripts.engineering.m13_bootstrap_publication import (
    PIN,
    publication_digest,
    publish_isolated_bootstrap,
    verify_isolated_bootstrap_binding,
)

from responsibleai.data_governance.backup_defense import (
    RestoreReadinessState,
    SqliteDurableLifecycleStateProvider,
)
from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.durable_intent import daemon_identity
from tests.test_stage3_bootstrap_store_preflight import fresh_target  # noqa: F401


def _crash_after_store_commit(url, store_path, store_key, profile_path, manifest, signatures):
    import asyncio

    import scripts.engineering.m13_bootstrap_publication as publisher

    from responsibleai.db.engine import create_engine

    original = publisher._inventory
    calls = 0

    def inventory(profile):
        nonlocal calls
        calls += 1
        if calls == 2:
            os._exit(23)
        return original(profile)

    publisher._inventory = inventory
    engine = create_engine(url)
    provider = SqliteDurableLifecycleStateProvider(store_path, secret_key=store_key)
    asyncio.run(
        publisher.publish_isolated_bootstrap(
            engine, provider, profile_path=profile_path, manifest=manifest, signatures=signatures
        )
    )


@pytest.fixture
async def publication(fresh_target, tmp_path):  # noqa: F811
    engine, provider, authorization_path, config = fresh_target
    keys = {role: Ed25519PrivateKey.generate() for role in config["operators"]}
    for role, key in keys.items():
        config["operators"][role]["public_key"] = key.public_key().public_bytes_raw().hex()
    authorization_path.write_text(json.dumps(config))
    docker = DockerContainerBackend().docker_cmd
    inventory = subprocess.run(
        [docker, "ps", "--all", "--no-trunc", "--format", "{{json .}}"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    # Disposable operators enroll this exact fixture inventory. This is NOT a
    # claim that arbitrary production containers are approved infrastructure.
    infrastructure = [json.loads(line)["ID"] for line in inventory.stdout.splitlines()]
    profile = {
        "purpose": "ISOLATED_BOOTSTRAP_PUBLICATION_V1",
        "authorization_profile": str(authorization_path),
        "store_b_path": str(provider.path),
        "docker_identity": daemon_identity(docker),
        "infrastructure_ids": infrastructure,
    }
    path = tmp_path / "publication.json"
    path.write_text(json.dumps(profile))
    path.chmod(0o600)
    evidence = await collect_bootstrap_store_evidence(
        engine, provider, profile_path=authorization_path
    )
    now = int(time.time())
    manifest = BootstrapManifest(
        installation_id=config["installation_id"],
        deployment_id=config["deployment_id"],
        environment=config["environment"],
        postgres_identity=config["postgres_identity"],
        store_b_identity=config["store_b_identity"],
        evidence_digest=publication_digest(evidence, profile),
        nonce=secrets.token_hex(32),
        created_at=now,
        expires_at=now + 240,
    )
    signatures = {
        config["operators"][role]["identity"]: base64.b64encode(
            key.sign(manifest.canonical_bytes())
        ).decode("ascii")
        for role, key in keys.items()
    }
    register_signed_new_installation(authorization_path, manifest, signatures)
    return engine, provider, path, manifest, signatures, config, profile


@pytest.mark.asyncio
async def test_signed_bootstrap_publishes_once_and_survives_provider_restart(
    publication, monkeypatch
):
    engine, provider, path, manifest, signatures, config, _ = publication
    assert provider.get_readiness_state() is None
    result = await publish_isolated_bootstrap(
        engine, provider, profile_path=path, manifest=manifest, signatures=signatures
    )
    assert result["state"] == "READY_VERIFIED" and result["production"] is False
    monkeypatch.setenv(PIN, str(path))
    restarted = SqliteDurableLifecycleStateProvider(provider.path, secret_key=provider._secret_key)
    assert restarted.get_readiness_state() == RestoreReadinessState.READY
    assert verify_isolated_bootstrap_binding(restarted)
    assert restarted.list_all() == []  # No tenant, root or execution authority.
    with pytest.raises((BootstrapRefusedError, sqlite3.Error)):
        await publish_isolated_bootstrap(
            engine, restarted, profile_path=path, manifest=manifest, signatures=signatures
        )
    with sqlite3.connect(config["registry"]) as external:
        external.execute("UPDATE bootstrap_publication SET phase='CONSUMED'")
    # Models crash after Store B commit, before external completion. READY in
    # the database is not usable admission, including after object restart.
    with pytest.raises(BootstrapRefusedError, match="incomplete"):
        restarted.get_readiness_state()


@pytest.mark.asyncio
@pytest.mark.parametrize("attack", ["expired", "wrong-deployment", "forged", "wrong-docker"])
async def test_bad_bootstrap_never_publishes_readiness(publication, attack):
    engine, provider, path, manifest, signatures, config, profile = publication
    if attack == "expired":
        manifest = replace(
            manifest, created_at=manifest.created_at - 600, expires_at=manifest.expires_at - 600
        )
    elif attack == "wrong-deployment":
        manifest = replace(manifest, deployment_id="substituted")
    elif attack == "forged":
        signatures = {key: base64.b64encode(bytes(64)).decode("ascii") for key in signatures}
    else:
        profile["docker_identity"] = "another-daemon"
        path.write_text(json.dumps(profile))
    with pytest.raises(BootstrapRefusedError):
        await publish_isolated_bootstrap(
            engine, provider, profile_path=path, manifest=manifest, signatures=signatures
        )
    assert provider.get_readiness_state() is None
    with sqlite3.connect(config["registry"]) as external:
        assert external.execute("SELECT state FROM installation").fetchone() == ("UNINITIALIZED",)


@pytest.mark.asyncio
async def test_real_process_crash_after_store_commit_never_admits_on_restart(publication):
    engine, provider, path, manifest, signatures, config, _ = publication
    worker = multiprocessing.get_context("spawn").Process(
        target=_crash_after_store_commit,
        args=(
            engine.raw.url.render_as_string(hide_password=False),
            str(provider.path),
            provider._secret_key,
            str(path),
            manifest,
            signatures,
        ),
    )
    worker.start()
    try:
        worker.join(30)
        assert worker.exitcode == 23
    finally:
        if worker.is_alive():
            worker.terminate()
            worker.join(5)
    restarted = SqliteDurableLifecycleStateProvider(provider.path, secret_key=provider._secret_key)
    with pytest.raises(BootstrapRefusedError, match="incomplete"):
        restarted.get_readiness_state()
    with sqlite3.connect(config["registry"]) as external:
        assert external.execute("SELECT phase FROM bootstrap_publication").fetchone() == (
            "CONSUMED",
        )
    with pytest.raises(BootstrapRefusedError):
        await publish_isolated_bootstrap(
            engine, restarted, profile_path=path, manifest=manifest, signatures=signatures
        )


@pytest.mark.asyncio
async def test_bootstrap_ready_rollback_cannot_erase_later_recovery_incident(publication):
    engine, provider, path, manifest, signatures, _, _ = publication
    await publish_isolated_bootstrap(
        engine, provider, profile_path=path, manifest=manifest, signatures=signatures
    )
    provider.set_readiness_state(RestoreReadinessState.FAILED)
    assert provider.get_readiness_state() == RestoreReadinessState.FAILED
    # Disposable fault injection represents restoring an older Store B image.
    # The independently retained installation incident fence is NOT rolled back.
    with sqlite3.connect(provider.path) as store:
        store.execute(
            "UPDATE durable_restore_readiness SET state='READY',epoch=1 WHERE key='global'"
        )
    restarted = SqliteDurableLifecycleStateProvider(provider.path, secret_key=provider._secret_key)
    with pytest.raises(BootstrapRefusedError, match="Signed R1 recovery required"):
        restarted.get_readiness_state()


@pytest.mark.asyncio
async def test_new_docker_workload_after_approval_is_not_ignored(publication):
    engine, provider, path, manifest, signatures, config, _ = publication
    docker = DockerContainerBackend().docker_cmd
    # Inert owned fixture: create only, never start, using the already installed
    # PostgreSQL qualification image. No unrelated container is removed.
    created = subprocess.run(
        [
            docker,
            "create",
            "--label",
            "io.whitepact.execution=bootstrap-negative-fixture",
            "postgres:16",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout.strip()
    assert re.fullmatch(r"[0-9a-f]{64}", created)
    try:
        with pytest.raises(BootstrapRefusedError, match="Unknown or execution workload"):
            await publish_isolated_bootstrap(
                engine, provider, profile_path=path, manifest=manifest, signatures=signatures
            )
        assert provider.get_readiness_state() is None
        with sqlite3.connect(config["registry"]) as external:
            assert external.execute("SELECT state FROM installation").fetchone() == (
                "UNINITIALIZED",
            )
    finally:
        subprocess.run([docker, "rm", created], check=True, capture_output=True, timeout=15)
