# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WP-AUD-015: authority-branch revocation must not leave a live subtree."""

from __future__ import annotations

import pytest

from responsibleai.db import DelegationRepository, create_engine
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository


async def _tree(repo: DelegationRepository) -> None:
    await repo.grant(
        "org-rev",
        "manager",
        granted_action_types=frozenset({"payment.execute", "report.read"}),
        purpose="manage",
        granted_by="owner",
    )
    await repo.grant(
        "org-rev",
        "worker",
        from_identity_id="manager",
        granted_action_types=frozenset({"report.read"}),
        purpose="ops",
        granted_by="manager",
    )
    await repo.grant(
        "org-rev",
        "leaf",
        from_identity_id="worker",
        granted_action_types=frozenset({"report.read"}),
        purpose="leaf",
        granted_by="worker",
    )


@pytest.mark.asyncio
async def test_revoke_branch_is_all_or_nothing_on_injected_crash() -> None:
    engine = create_engine(":memory:")
    await engine.init()
    repo = DelegationRepository(engine)
    epochs = RevocationEpochRepository(engine)
    await _tree(repo)
    before = await epochs.current("org-rev")

    import responsibleai.db.delegation_repository as mod

    original = mod.bump_epoch_on_connection

    async def crash_after_epoch(conn, organization_id, scope="governance"):
        await original(conn, organization_id, scope)
        raise RuntimeError("injected crash after epoch bump")

    mod.bump_epoch_on_connection = crash_after_epoch
    try:
        with pytest.raises(RuntimeError, match="injected crash"):
            await repo.revoke_branch("org-rev", "manager", revoked_by="owner", reason="offboard")
    finally:
        mod.bump_epoch_on_connection = original

    after = await epochs.current("org-rev")
    assert after.epoch == before.epoch
    assert (await repo.get_active_delegation("org-rev", "manager")) is not None
    assert (await repo.get_active_delegation("org-rev", "worker")) is not None
    leaf = await repo.get_active_delegation("org-rev", "leaf")
    assert leaf is not None
    assert leaf.is_active()
    await engine.close()


@pytest.mark.asyncio
async def test_successful_branch_revocation_kills_descendant_authority_and_bumps_epoch() -> None:
    engine = create_engine(":memory:")
    await engine.init()
    repo = DelegationRepository(engine)
    epochs = RevocationEpochRepository(engine)
    await _tree(repo)
    before = await epochs.current("org-rev")
    revoked = await repo.revoke_branch("org-rev", "manager", revoked_by="owner", reason="offboard")
    assert len(revoked) == 3
    after = await epochs.current("org-rev")
    assert after.epoch == before.epoch + 1
    assert await repo.get_active_delegation("org-rev", "manager") is None
    assert await repo.get_active_delegation("org-rev", "worker") is None
    assert await repo.get_active_delegation("org-rev", "leaf") is None
    await engine.close()


@pytest.mark.asyncio
async def test_revoke_branch_uses_single_transaction_boundary() -> None:
    import inspect

    from responsibleai.db.delegation_repository import DelegationRepository as Repo

    source = inspect.getsource(Repo.revoke_branch)
    assert source.count("async with self._engine.raw.begin()") == 1
    assert "bump_epoch_on_connection" in source
    assert ".id.in_(revoked_ids)" in source
    assert source.find("bump_epoch_on_connection") < source.find(".id.in_(revoked_ids)")
