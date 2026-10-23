# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Independent regression oracles for immutable tenant lifecycle authority."""

from dataclasses import replace

import pytest

from responsibleai.data_governance.backup_defense import (
    InMemoryLifecycleStateProvider,
    LifecycleRollbackError,
    LifecycleState,
    LifecycleStateRecord,
    SqliteDurableLifecycleStateProvider,
)


@pytest.fixture(params=["durable", "memory"])
def established(tmp_path, request):
    provider = (
        SqliteDurableLifecycleStateProvider(tmp_path / "isolated-b.sqlite3")
        if request.param == "durable"
        else InMemoryLifecycleStateProvider()
    )
    original = LifecycleStateRecord(
        tenant_id="disposable-tenant",
        generation_id="original-generation",
        state=LifecycleState.ACTIVE,
        effective_at="2026-10-23T00:00:00+00:00",
        security_epoch=7,
        revocation_floor=6,
    )
    provider.record_state(original)
    return provider, original


def test_generation_cannot_be_replaced_even_with_increased_epoch(established):
    provider, original = established
    with pytest.raises(LifecycleRollbackError, match="generation"):
        provider.record_state(
            replace(
                original,
                generation_id="attacker-selected-replacement",
                security_epoch=8,
                effective_at="2026-10-23T00:00:01+00:00",
            )
        )
    assert provider.get_state(original.tenant_id).generation_id == original.generation_id


@pytest.mark.parametrize("epoch", [7, 8])
def test_revocation_floor_cannot_decrease_independently_of_epoch(established, epoch):
    provider, original = established
    with pytest.raises(LifecycleRollbackError, match="floor"):
        provider.record_state(
            replace(
                original,
                security_epoch=epoch,
                revocation_floor=5,
                effective_at="2026-10-23T00:00:01+00:00",
            )
        )
    assert provider.get_state(original.tenant_id).revocation_floor == 6


@pytest.mark.parametrize("established", ["durable"], indirect=True)
def test_legitimate_same_generation_monotonic_update_survives_restart(established):
    provider, original = established
    provider.record_state(
        replace(
            original,
            security_epoch=8,
            revocation_floor=7,
            effective_at="2026-10-23T00:00:01+00:00",
        )
    )
    restarted = SqliteDurableLifecycleStateProvider(provider.path)
    actual = restarted.get_state(original.tenant_id)
    assert (actual.generation_id, actual.security_epoch, actual.revocation_floor) == (
        original.generation_id,
        8,
        7,
    )
    assert restarted.verify_integrity()


def test_tombstone_never_resurrects(established):
    provider, original = established
    provider.record_state(replace(original, state=LifecycleState.TOMBSTONED))
    with pytest.raises(LifecycleRollbackError):
        provider.record_state(replace(original, security_epoch=9))
    assert provider.get_state(original.tenant_id).state == LifecycleState.TOMBSTONED


def test_stricter_floor_is_not_dropped_as_duplicate(established):
    provider, original = established
    provider.record_state(replace(original, revocation_floor=7))
    assert provider.get_state(original.tenant_id).revocation_floor == 7
