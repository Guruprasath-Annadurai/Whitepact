# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real durable storage tests, NOT protected controller/admission qualification."""

import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

import pytest

from responsibleai.data_governance.backup_defense import SqliteDurableLifecycleStateProvider
from responsibleai.data_governance.tenant_provisioning import (
    PendingTenantReservations,
    ProvisioningReservationError,
)


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("WHITEPACT_ENV", "test")
    provider = SqliteDurableLifecycleStateProvider(tmp_path / "disposable-store-b.sqlite3")
    registry = PendingTenantReservations(provider)
    registry.initialize()
    return provider, registry


def reserve(registry, **changes):
    request = {
        "deployment_id": "isolated-deployment",
        "request_id": "creation-1",
        "principal_id": "test-principal",
        "operation_digest": "a" * 64,
    }
    return registry.reserve(**(request | changes))


def test_random_256_bit_generation_and_no_active_lifecycle(ledger):
    provider, registry = ledger
    identity = reserve(registry)
    assert re.fullmatch(r"[a-f0-9]{64}", identity.generation_id)
    assert identity.status == "PENDING"
    assert provider.get_state(identity.tenant_id) is None
    assert provider.list_all() == []
    other = reserve(registry, request_id="creation-2")
    assert other.tenant_id != identity.tenant_id
    assert other.generation_id != identity.generation_id


def test_retry_after_reopen_preserves_exact_identity(ledger):
    provider, registry = ledger
    original = reserve(registry)
    reopened = PendingTenantReservations(SqliteDurableLifecycleStateProvider(provider.path))
    assert asdict(reserve(reopened)) == asdict(original)


@pytest.mark.parametrize(
    "changes", [{"principal_id": "another-principal"}, {"operation_digest": "b" * 64}]
)
def test_conflicting_request_never_reassigns_generation(ledger, changes):
    _, registry = ledger
    original = reserve(registry)
    with pytest.raises(ProvisioningReservationError, match="conflict"):
        reserve(registry, **changes)
    assert reserve(registry) == original


def test_concurrent_reservation_has_one_durable_identity(ledger):
    provider, registry = ledger
    with ThreadPoolExecutor(max_workers=8) as executor:
        identities = list(executor.map(lambda _: reserve(registry), range(16)))
    assert len({identity.generation_id for identity in identities}) == 1
    with sqlite3.connect(provider.path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM tenant_provisioning_reservations"
        ).fetchone() == (1,)
    assert provider.list_all() == []


@pytest.mark.parametrize("action", ["UPDATE", "DELETE"])
def test_sql_mutation_of_pending_identity_is_refused(ledger, action):
    provider, registry = ledger
    original = reserve(registry)
    statement = (
        "UPDATE tenant_provisioning_reservations SET generation_id=?"
        if action == "UPDATE"
        else "DELETE FROM tenant_provisioning_reservations WHERE generation_id=?"
    )
    with sqlite3.connect(provider.path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(statement, (original.generation_id,))
    assert reserve(registry) == original


def test_reserve_never_initializes_missing_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("WHITEPACT_ENV", "test")
    provider = SqliteDurableLifecycleStateProvider(tmp_path / "store-b.sqlite3")
    registry = PendingTenantReservations(provider)
    with pytest.raises(ProvisioningReservationError, match="unavailable"):
        reserve(registry)
    assert provider.list_all() == []


def test_caller_cannot_supply_generation(ledger):
    provider, registry = ledger
    with pytest.raises(TypeError):
        reserve(registry, generation_id="f" * 64)
    with sqlite3.connect(provider.path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM tenant_provisioning_reservations"
        ).fetchone() == (0,)


def test_production_refused_even_for_preexisting_instance(ledger, monkeypatch):
    provider, registry = ledger
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    with pytest.raises(ProvisioningReservationError, match="not production qualified"):
        reserve(registry)
    with pytest.raises(ProvisioningReservationError, match="not production qualified"):
        PendingTenantReservations(provider)
    with pytest.raises(ProvisioningReservationError, match="not production qualified"):
        registry.initialize()
