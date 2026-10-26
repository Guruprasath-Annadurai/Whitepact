# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real Store B replay/crash tests; no PostgreSQL or activation claim."""

import base64
import multiprocessing
import os
import secrets
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from responsibleai.data_governance.backup_defense import (
    RestoreReadinessState,
    SqliteDurableLifecycleStateProvider,
)
from responsibleai.data_governance.provisioning_manifest import (
    ProvisionerTrust,
    ProvisioningAuthorizationError,
    ProvisioningManifest,
)
from responsibleai.data_governance.tenant_provisioning import (
    PendingTenantReservations,
    PublicationAuthorizationLedger,
)


@pytest.fixture
def enrolled(tmp_path, monkeypatch):
    monkeypatch.setenv("WHITEPACT_ENV", "test")
    provider = SqliteDurableLifecycleStateProvider(
        tmp_path / "isolated-b.sqlite3", secret_key=secrets.token_hex(32)
    )
    provider.set_readiness_state(RestoreReadinessState.READY)
    pending = PendingTenantReservations(provider)
    pending.initialize()
    reservation = pending.reserve(
        deployment_id="disposable",
        request_id="request-1",
        principal_id="user-1",
        operation_digest="a" * 64,
    )
    key = Ed25519PrivateKey.generate()
    ledger = PublicationAuthorizationLedger(provider)
    ledger.initialize(
        ProvisionerTrust(
            "test-controller",
            key.public_key().public_bytes_raw(),
            "disposable",
            "test",
            "pg-test",
            "b-test",
        )
    )
    now = int(time.time())
    manifest = ProvisioningManifest(
        deployment_id="disposable",
        environment="test",
        postgres_identity="pg-test",
        store_b_identity="b-test",
        request_id=reservation.request_id,
        principal_id=reservation.principal_id,
        tenant_id=reservation.tenant_id,
        generation_id=reservation.generation_id,
        operation_digest=reservation.operation_digest,
        pending_receipt_digest="b" * 64,
        readiness_epoch=1,
        security_epoch=1,
        revocation_floor=1,
        created_at=now - 1,
        expires_at=now + 59,
        nonce="c" * 64,
        controller_id="test-controller",
    )
    return provider, ledger, manifest, key


def signature(key, manifest):
    return base64.b64encode(key.sign(manifest.canonical_bytes())).decode("ascii")


def consume(ledger, manifest, encoded):
    return ledger.consume(manifest, encoded)


@pytest.mark.parametrize("fault", ["missing", "mismatched"])
def test_publication_read_rejects_lost_or_corrupt_pending_intent(enrolled, fault):
    provider, ledger, manifest, key = enrolled
    ledger.publish(manifest, signature(key, manifest))
    assert ledger.publication(manifest.tenant_id) == manifest
    # Administrative fault injection in a disposable database, not a supported
    # lifecycle operation. Ordinary writes are rejected by immutable triggers.
    connection = provider._get_connection()
    try:
        connection.execute("DROP TRIGGER tenant_reservation_no_delete")
        connection.execute("DROP TRIGGER tenant_reservation_no_update")
        if fault == "missing":
            connection.execute("DELETE FROM tenant_provisioning_reservations")
        else:
            connection.execute(
                "UPDATE tenant_provisioning_reservations SET operation_digest=?", ("f" * 64,)
            )
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(ProvisioningAuthorizationError, match="Publication evidence is unverified"):
        ledger.publication(manifest.tenant_id)


def test_consumption_is_durable_and_never_means_active(enrolled):
    provider, ledger, manifest, key = enrolled
    assert consume(ledger, manifest, signature(key, manifest)) == manifest.digest()
    reopened = PublicationAuthorizationLedger(
        SqliteDurableLifecycleStateProvider(provider.path, secret_key=provider._secret_key)
    )
    with pytest.raises(ProvisioningAuthorizationError, match="replay"):
        consume(reopened, manifest, signature(key, manifest))
    assert provider.get_state(manifest.tenant_id) is None


def test_authorized_publication_is_atomic_with_consumption_not_completion(enrolled):
    provider, ledger, manifest, key = enrolled
    encoded = signature(key, manifest)
    digest = ledger.publish(manifest, encoded)
    actual = provider.get_state(manifest.tenant_id)
    assert actual.generation_id == manifest.generation_id
    assert actual.security_epoch == manifest.security_epoch
    assert actual.revocation_floor == manifest.revocation_floor
    assert provider.verify_integrity()
    with sqlite3.connect(provider.path) as connection:
        assert connection.execute(
            "SELECT manifest_digest FROM provisioning_publication_consumptions WHERE tenant_id=?",
            (manifest.tenant_id,),
        ).fetchone() == (digest,)
    with pytest.raises(ProvisioningAuthorizationError):
        ledger.publish(manifest, encoded)


def test_invalid_signature_cannot_publish_active_or_consume(enrolled):
    provider, ledger, manifest, _ = enrolled
    attacker = Ed25519PrivateKey.generate()
    with pytest.raises(ProvisioningAuthorizationError, match="signature"):
        ledger.publish(manifest, signature(attacker, manifest))
    assert provider.get_state(manifest.tenant_id) is None
    with sqlite3.connect(provider.path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM provisioning_publication_consumptions"
        ).fetchone() == (0,)


def test_publication_failure_rolls_back_consumption(enrolled):
    provider, ledger, manifest, key = enrolled
    with sqlite3.connect(provider.path) as connection:
        connection.execute(
            "CREATE TRIGGER injected_disk_failure BEFORE INSERT ON durable_tenant_lifecycle_states "
            "BEGIN SELECT RAISE(ABORT,'injected storage failure'); END"
        )
    with pytest.raises(ProvisioningAuthorizationError):
        ledger.publish(manifest, signature(key, manifest))
    with sqlite3.connect(provider.path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM provisioning_publication_consumptions"
        ).fetchone() == (0,)
    assert provider.get_state(manifest.tenant_id) is None


def test_competing_consumers_have_exactly_one_winner(enrolled):
    provider, ledger, manifest, key = enrolled
    encoded = signature(key, manifest)

    def attempt(_):
        try:
            consume(ledger, manifest, encoded)
            return True
        except ProvisioningAuthorizationError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(16)))
    assert results.count(True) == 1
    assert provider.get_state(manifest.tenant_id) is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("principal_id", "other"),
        ("generation_id", "d" * 64),
        ("operation_digest", "d" * 64),
        ("tenant_id", "other"),
        ("request_id", "other"),
    ],
)
def test_even_valid_controller_signature_requires_exact_pending_binding(enrolled, field, value):
    provider, ledger, manifest, key = enrolled
    changed = replace(manifest, **{field: value})
    with pytest.raises(ProvisioningAuthorizationError, match="reservation"):
        consume(ledger, changed, signature(key, changed))
    # An invalid attempt does not insert a consumption or modify the reservation.
    with sqlite3.connect(provider.path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM provisioning_publication_consumptions"
        ).fetchone() == (0,)
    assert provider.get_state(manifest.tenant_id) is None


def test_caller_cannot_reenroll_another_controller(enrolled):
    provider, ledger, manifest, _ = enrolled
    attacker = Ed25519PrivateKey.generate()
    with pytest.raises(sqlite3.OperationalError):
        ledger.initialize(
            ProvisionerTrust(
                "test-controller",
                attacker.public_key().public_bytes_raw(),
                "disposable",
                "test",
                "pg-test",
                "b-test",
            )
        )
    with pytest.raises(ProvisioningAuthorizationError, match="signature"):
        consume(ledger, manifest, signature(attacker, manifest))
    assert provider.get_state(manifest.tenant_id) is None


def crash_after_consumption(path, manifest, encoded, integrity_key):
    provider = SqliteDurableLifecycleStateProvider(path, secret_key=integrity_key)
    consume(PublicationAuthorizationLedger(provider), manifest, encoded)
    os._exit(23)


def test_process_death_after_commit_preserves_single_use_and_no_active(enrolled):
    provider, ledger, manifest, key = enrolled
    encoded = signature(key, manifest)
    child = multiprocessing.get_context("spawn").Process(
        target=crash_after_consumption,
        args=(provider.path, manifest, encoded, provider._secret_key),
    )
    child.start()
    child.join(timeout=15)
    try:
        assert child.exitcode == 23
        with pytest.raises(ProvisioningAuthorizationError, match="replay"):
            consume(ledger, manifest, encoded)
        assert provider.get_state(manifest.tenant_id) is None
    finally:
        if child.is_alive():
            child.kill()
            child.join(timeout=5)
