# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Genuine enrolled-owner authority contracts and transaction rollback receipts.

The owner fixture verifies email and authenticates an enrolled signing key through
the server. These component receipts do not certify physical authenticators or SMTP.
"""

import base64
import uuid

import pytest
from sqlalchemy import func, select

from responsibleai.db.engine import (
    governance_consent_proofs,
    governance_delegations,
    governance_root_authority_records,
    trust_fabric_bootstrap_records,
)
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.enterprise.authority.service import CustomerAuthorityService
from responsibleai.enterprise.errors import EnterpriseError
from tests.test_sovereign_authority import owner as owner
from tests.test_sovereign_authority import root


async def active_counts(engine, org_id):
    async with engine.raw.connect() as conn:
        counts = []
        for table, organization_column in (
            (
                governance_root_authority_records,
                governance_root_authority_records.c.organization_id,
            ),
            (governance_consent_proofs, governance_consent_proofs.c.organization_id),
            (governance_delegations, governance_delegations.c.org_id),
        ):
            counts.append(
                await conn.scalar(
                    select(func.count())
                    .select_from(table)
                    .where(organization_column == org_id, table.c.revoked_at.is_(None))
                )
            )
        return tuple(counts)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("token", ""),
        ("nonce", ""),
        ("scope_description", "   "),
        ("purpose", "\t"),
        ("allowed_action_types", []),
        ("allowed_targets", []),
        ("key_algorithm", "RSA"),
        ("root_signature", base64.urlsafe_b64encode(b"x" * 64).decode()),
        ("token", "incorrect-token"),
        ("nonce", "incorrect-nonce"),
    ],
)
async def test_invalid_completion_cannot_consume_legitimate_ceremony(owner, field, invalid):
    service, actor, parameters = await root(owner, prepare_only=True)
    engine = owner[0]
    attempt = dict(parameters, **{field: invalid})
    with pytest.raises(EnterpriseError):
        await service.complete_root_bootstrap(actor, **attempt)
    assert await active_counts(engine, actor.org_id) == (0, 0, 0)
    async with engine.raw.connect() as conn:
        ceremony = (
            await conn.execute(
                select(trust_fabric_bootstrap_records).where(
                    trust_fabric_bootstrap_records.c.org_id == actor.org_id,
                    trust_fabric_bootstrap_records.c.nonce == parameters["nonce"],
                )
            )
        ).one()
        assert ceremony.consumed_at is None
    # In particular, failures after WebAuthn verification must roll back challenge
    # consumption and authenticator counters, allowing this genuine assertion once.
    await service.complete_root_bootstrap(actor, **parameters)
    assert await active_counts(engine, actor.org_id) == (1, 1, 1)
    with pytest.raises(EnterpriseError):
        await service.complete_root_bootstrap(actor, **parameters)
    assert await active_counts(engine, actor.org_id) == (1, 1, 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("owner", ["sqlite", "postgres"], indirect=True)
async def test_root_revocation_cascades_real_grant_and_missing_root_rolls_back_epoch(owner):
    engine, _, actor, *_ = owner
    await root(owner)
    service = CustomerAuthorityService(engine)
    agent = await service.register_agent(actor, org_id=actor.org_id, name="revocable")
    grant = await service.delegate_to_agent(
        actor,
        org_id=actor.org_id,
        agent_id=agent["agent_id"],
        granted_action_types=["rai_policy_check"],
        allowed_targets=["rai_policy_check"],
        purpose="Explicit revocation regression",
    )
    before = await service.get_authority_status(actor, org_id=actor.org_id)
    assert before["has_active_authority"] is True
    assert await active_counts(engine, actor.org_id) == (1, 2, 2)
    with pytest.raises(EnterpriseError):
        await service.revoke_root_authority(
            actor, org_id=actor.org_id, root_id="missing-root", reason="invalid request"
        )
    unchanged = await service.get_authority_status(actor, org_id=actor.org_id)
    assert unchanged == before
    receipt = await service.revoke_root_authority(
        actor,
        org_id=actor.org_id,
        root_id=before["root_authority"]["root_id"],
        reason="Customer withdrew consent",
    )
    assert receipt["new_epoch"] == before["revocation_epoch"] + 1
    assert await active_counts(engine, actor.org_id) == (0, 0, 0)
    after = await service.get_authority_status(actor, org_id=actor.org_id)
    assert after["has_active_authority"] is False
    assert after["root_authority"] is None
    async with engine.raw.connect() as conn:
        revoked = (
            await conn.execute(
                select(governance_delegations).where(
                    governance_delegations.c.id == grant["delegation_id"]
                )
            )
        ).one()
        assert revoked.revoked_at is not None
    with pytest.raises(EnterpriseError):
        await service.delegate_to_agent(
            actor,
            org_id=actor.org_id,
            agent_id=agent["agent_id"],
            granted_action_types=["rai_policy_check"],
            allowed_targets=["rai_policy_check"],
            purpose="Must not resurrect revoked authority",
        )
    assert await active_counts(engine, actor.org_id) == (0, 0, 0)


@pytest.mark.asyncio
async def test_application_inventory_and_disable_preserve_unrelated_agent_authority(owner):
    engine, _, actor, *_ = owner
    await root(owner)
    service = CustomerAuthorityService(engine)
    application = await service.register_application(
        actor, org_id=actor.org_id, name=" Customer application ", description=" Local only "
    )
    attached = await service.register_agent(
        actor, org_id=actor.org_id, name="attached", application_id=application["application_id"]
    )
    unrelated = await service.register_agent(actor, org_id=actor.org_id, name="unrelated")
    for agent in (attached, unrelated):
        await service.delegate_to_agent(
            actor,
            org_id=actor.org_id,
            agent_id=agent["agent_id"],
            granted_action_types=["rai_policy_check"],
            allowed_targets=["rai_policy_check"],
            purpose="Explicit application scope regression",
        )
    inventory = await service.list_applications(actor, org_id=actor.org_id)
    assert len(inventory) == 1
    assert inventory[0]["agent_count"] == 1
    assert inventory[0]["has_execution_authority"] is False
    detail = await service.get_application(
        actor, org_id=actor.org_id, app_id=application["application_id"]
    )
    assert detail["name"] == "Customer application"
    assert detail["description"] == "Local only"
    assert [a["agent_id"] for a in detail["agents"]] == [attached["agent_id"]]
    assert detail["agents"][0]["has_active_delegation"] is True
    receipt = await service.disable_application(
        actor, org_id=actor.org_id, app_id=application["application_id"]
    )
    assert receipt["disabled_agents"] == [attached["agent_id"]]
    agents = {a["agent_id"]: a for a in await service.list_agents(actor, org_id=actor.org_id)}
    assert agents[attached["agent_id"]]["lifecycle_state"] == "DISABLED"
    assert agents[attached["agent_id"]]["has_active_delegation"] is False
    assert agents[unrelated["agent_id"]]["lifecycle_state"] == "ACTIVE"
    assert agents[unrelated["agent_id"]]["has_active_delegation"] is True
    assert await active_counts(engine, actor.org_id) == (1, 2, 2)
    with pytest.raises(EnterpriseError):
        await service.register_agent(
            actor,
            org_id=actor.org_id,
            name="late registration",
            application_id=application["application_id"],
        )


@pytest.mark.asyncio
async def test_inventory_denials_cannot_create_authority_or_advance_epoch(owner):
    engine, _, actor, *_ = owner
    service = CustomerAuthorityService(engine)
    epochs = RevocationEpochRepository(engine)
    before = await epochs.current(actor.org_id)
    agent = await service.register_agent(actor, org_id=actor.org_id, name="No implicit authority")
    assert agent["has_delegated_authority"] is False
    assert await service.list_applications(actor, org_id=actor.org_id) == []
    attempts = [
        service.register_application(actor, org_id=actor.org_id, name="   "),
        service.register_agent(actor, org_id=actor.org_id, name="  "),
        service.register_agent(actor, org_id=actor.org_id, name="orphan", application_id="absent"),
        service.get_application(actor, org_id=actor.org_id, app_id="absent"),
        service.disable_application(actor, org_id=actor.org_id, app_id="absent"),
        service.disable_agent(actor, org_id=actor.org_id, agent_id="absent"),
        service.delegate_to_agent(
            actor,
            org_id=actor.org_id,
            agent_id="absent",
            granted_action_types=["rai_policy_check"],
            allowed_targets=["rai_policy_check"],
            purpose="Missing agent cannot receive consent",
        ),
        service.delegate_to_agent(
            actor,
            org_id=actor.org_id,
            agent_id=agent["agent_id"],
            granted_action_types=["rai_policy_check"],
            allowed_targets=["rai_policy_check"],
            purpose="Registration cannot substitute for root authority",
        ),
        service.list_applications(actor, org_id=str(uuid.uuid4())),
        service.list_agents(actor, org_id=str(uuid.uuid4())),
    ]
    # Await every created coroutine even if an earlier contract regresses.
    outcomes = []
    for attempt in attempts:
        try:
            outcomes.append(await attempt)
        except EnterpriseError as exc:
            outcomes.append(exc)
    assert all(isinstance(outcome, EnterpriseError) for outcome in outcomes)
    assert (await epochs.current(actor.org_id)).epoch == before.epoch
    assert await active_counts(engine, actor.org_id) == (0, 0, 0)
    agents = await service.list_agents(actor, org_id=actor.org_id)
    assert len(agents) == 1
    assert agents[0]["agent_id"] == agent["agent_id"]
    assert agents[0]["has_active_delegation"] is False
