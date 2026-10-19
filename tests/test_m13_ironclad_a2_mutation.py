# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Genuine A2 ceremony with independently committed revocation fault injection."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, insert, select, update

import responsibleai.enterprise.authority.service as service_module
from responsibleai.db.engine import governance_root_authority_records, trust_fabric_principals
from responsibleai.enterprise.errors import EnterpriseError
from tests.test_sovereign_authority import owner as owner
from tests.test_sovereign_authority import root


@pytest.mark.asyncio
@pytest.mark.parametrize("owner", ["postgres"], indirect=True)
@pytest.mark.parametrize("state", ["REVOKED", "SUSPENDED", "DISABLED", "DELETED"])
async def test_principal_revocation_before_locked_authorization_cannot_activate_root(
    owner, state, monkeypatch
):
    service, actor, parameters = await root(owner, prepare_only=True)
    engine = owner[0]
    now = datetime.now(UTC).isoformat()
    # Non-authoritative pending identity, not a seeded privileged principal.
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(trust_fabric_principals).values(
                id=actor.user_id,
                org_id=actor.org_id,
                principal_type="HUMAN",
                display_name="Pending owner",
                lifecycle_state="PENDING_VERIFICATION",
                created_at=now,
                updated_at=now,
            )
        )
    original = service_module.require_recent_owner
    changed = False

    async def revoke_before_locked_context(conn, current_actor, org_id):
        nonlocal changed
        if not changed:
            changed = True
            async with engine.raw.begin() as independent:
                await independent.execute(
                    update(trust_fabric_principals)
                    .where(trust_fabric_principals.c.id == actor.user_id)
                    .values(lifecycle_state=state)
                )
        return await original(conn, current_actor, org_id)

    monkeypatch.setattr(service_module, "require_recent_owner", revoke_before_locked_context)
    with pytest.raises(EnterpriseError):
        await service.complete_root_bootstrap(actor, **parameters)
    async with engine.raw.connect() as conn:
        assert (
            await conn.scalar(
                select(trust_fabric_principals.c.lifecycle_state).where(
                    trust_fabric_principals.c.id == actor.user_id
                )
            )
            == state
        )
        assert (
            await conn.scalar(
                select(func.count())
                .select_from(governance_root_authority_records)
                .where(governance_root_authority_records.c.organization_id == actor.org_id)
            )
            == 0
        )
