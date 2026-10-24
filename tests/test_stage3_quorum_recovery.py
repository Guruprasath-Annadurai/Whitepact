# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real invitation/UV-session successors; historical test bytes remain immutable."""

from dataclasses import replace

import pytest
from sqlalchemy import select, update

from responsibleai.db.engine import (
    authority_recovery_requests,
    authority_recovery_votes,
    governance_consent_proofs,
    governance_root_authority_records,
    trust_fabric_principals,
    trust_fabric_trust_roots,
    web_memberships,
    web_users,
)
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.enterprise.authority.service import CustomerAuthorityService
from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.enterprise.runtime import get_enterprise_engine
from responsibleai.enterprise.security.service import IdentitySecurityService
from responsibleai.enterprise.security.webauthn import b64url_decode
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.rbac.models import Role
from tests import test_m12fs_root_hardening as historical
from tests.test_m12fs_root_hardening import _configure_test_env  # noqa: F401
from tests.webauthn_fakes import assertion_blob


@pytest.fixture
def qualified_voters(monkeypatch):
    owners = {}
    original_owner = historical._create_test_owner
    receipts = {}

    async def owner(*args, **kwargs):
        result = await original_owner(*args, **kwargs)
        owners[result[2]] = result[0]
        return result

    async def invited_admin(org_id, email, role=Role.ADMIN):
        engine = get_enterprise_engine()
        # Use an already legitimately enrolled customer identity. The current
        # first-passkey policy admits initial owners, not password-only invitees.
        # Provision an independent workspace through the actual controller;
        # never seed a voter membership or PASSKEY_UV flag to bypass that policy.
        _, user_id, _, _, _ = await original_owner(
            email=email, org_slug="voter-" + email.split("@")[0]
        )
        iam = EnterpriseIAM(engine)
        _, invitation = await iam.invite_member(owners[org_id], org_id, email=email, role=role)
        accepted = await iam.accept_invitation(token=invitation, user_id=user_id)
        assert accepted == org_id
        identity = IdentitySecurityService(engine, origin="http://localhost", rp_id="localhost")
        key, credential = historical._OWNER_SIGNERS[user_id]
        ceremony = await identity.begin_webauthn(
            user_id=None, session_id=None, ceremony="authenticate"
        )
        client, auth, signature = assertion_blob(
            rp_id="localhost",
            origin="http://localhost",
            challenge=b64url_decode(ceremony["challenge"]),
            private_key=key,
            sign_count=2,
        )
        token, csrf, session = await identity.authenticate_passkey(
            client_data_b64=client,
            authenticator_data_b64=auth,
            signature_b64=signature,
            credential_id=credential,
            org_id=org_id,
        )
        actor = Actor(
            actor_type="USER",
            actor_id=user_id,
            user_id=user_id,
            org_id=org_id,
            role=role,
            membership_status="ACTIVE",
        )
        actor = replace(actor, session_id=session.session_id)
        async with engine.raw.connect() as conn:
            member = (
                await conn.execute(
                    select(web_memberships).where(
                        web_memberships.c.user_id == user_id, web_memberships.c.org_id == org_id
                    )
                )
            ).one()
            assert member.invited_by_user_id == owners[org_id].user_id
            assert member.accepted_at is not None and member.status == "ACTIVE"
        assert session.phishing_resistant
        receipts[user_id] = actor
        return actor, user_id, token, csrf

    monkeypatch.setattr(historical, "_create_test_owner", owner)
    monkeypatch.setattr(historical, "_create_additional_admin", invited_admin)
    return receipts


@pytest.mark.asyncio
async def test_invited_uv_quorum_preserves_historical_lifecycle(qualified_voters):
    # Execute every original self-vote, duplicate, pre-quorum, once-only and
    # resulting-authority assertion with real invite acceptance and UV sessions.
    await historical.test_quorum_recovery_full_lifecycle_2_of_3()
    engine = get_enterprise_engine()
    async with engine.raw.connect() as conn:
        request = (await conn.execute(select(authority_recovery_requests))).one()
        votes = (await conn.execute(select(authority_recovery_votes))).all()
        root = (await conn.execute(select(trust_fabric_trust_roots))).one()
        principal = (
            await conn.execute(
                select(trust_fabric_principals).where(
                    trust_fabric_principals.c.id == root.root_principal_id
                )
            )
        ).one()
        current = (
            await conn.execute(
                select(governance_root_authority_records).where(
                    governance_root_authority_records.c.revoked_at.is_(None)
                )
            )
        ).one()
    assert request.status == "EXECUTED"
    assert len(votes) == 2 and len({v.voter_user_id for v in votes}) == 2
    assert request.requester_user_id not in {v.voter_user_id for v in votes}
    assert request.executed_by_user_id in qualified_voters
    assert principal.id == current.subject_id == request.requester_user_id
    assert principal.org_id == current.organization_id == request.org_id
    assert principal.principal_type == "HUMAN" and principal.lifecycle_state == "ACTIVE"


@pytest.mark.asyncio
async def test_invited_uv_deactivated_voter_is_not_counted(qualified_voters):
    await historical.test_quorum_pre_execution_deactivation_check()
    engine = get_enterprise_engine()
    async with engine.raw.connect() as conn:
        request = (await conn.execute(select(authority_recovery_requests))).one()
        roots = (await conn.execute(select(governance_root_authority_records))).all()
    assert len(qualified_voters) == 2
    assert request.status == "PENDING" and request.executed_at is None
    assert len(roots) == 1 and roots[0].revoked_at is None


@pytest.fixture
async def approved_recovery(qualified_voters):
    owner, _, org_id, _, _ = await historical._create_test_owner()
    target, target_id, _, _ = await historical._create_additional_admin(org_id, "target@test.local")
    voter, voter_id, _, _ = await historical._create_additional_admin(org_id, "voter@test.local")
    engine = get_enterprise_engine()
    service = CustomerAuthorityService(engine)
    ceremony = await service.initiate_root_bootstrap(owner, org_id=org_id)
    root = await service.complete_root_bootstrap(
        owner,
        org_id=org_id,
        token=ceremony["token"],
        nonce=ceremony["nonce"],
        **await historical._qualified_bootstrap_arguments(service, owner, ceremony),
        scope_description="Recovery regression",
        purpose="Disposable qualification",
        allowed_action_types=["read"],
        allowed_targets=["qualification"],
    )
    request = await service.create_recovery_request(
        target,
        org_id=org_id,
        request_type="ROOT_RECOVERY",
        target_root_id=root["root_id"],
        proposed_parameters={"new_owner_user_id": target_id},
        required_quorum_m=2,
        eligible_quorum_n=3,
    )
    for actor in (owner, voter):
        await service.vote_recovery_request(
            actor,
            org_id=org_id,
            request_id=request["request_id"],
            action_digest=request["action_digest"],
            decision="APPROVE",
        )
    return service, owner, target_id, voter_id, org_id, request


async def recovery_snapshot(engine, org_id):
    async with engine.raw.connect() as conn:
        rows = {}
        for table in (
            authority_recovery_requests,
            authority_recovery_votes,
            governance_root_authority_records,
            governance_consent_proofs,
            trust_fabric_principals,
            trust_fabric_trust_roots,
        ):
            result = (await conn.execute(select(table))).mappings().all()
            rows[table.name] = sorted([dict(row) for row in result], key=lambda row: str(row))
    rows["epoch"] = (await RevocationEpochRepository(engine).current(org_id)).epoch
    return rows


@pytest.mark.asyncio
async def test_late_failure_rolls_back_principal_root_epoch_and_consumption(
    approved_recovery, monkeypatch
):
    service, owner, _, _, org_id, request = approved_recovery
    engine = get_enterprise_engine()
    before = await recovery_snapshot(engine, org_id)
    original_record = service._audit.record

    async def interrupted(**kwargs):
        if kwargs["action"] == "RECOVERY_REQUEST_EXECUTED":
            raise RuntimeError("qualification transaction interruption")
        return await original_record(**kwargs)

    monkeypatch.setattr(service._audit, "record", interrupted)
    with pytest.raises(RuntimeError, match="qualification transaction interruption"):
        await service.execute_recovery_request(
            owner,
            org_id=org_id,
            request_id=request["request_id"],
            action_digest=request["action_digest"],
        )
    assert await recovery_snapshot(engine, org_id) == before
    async with engine.raw.connect() as conn:
        assert await conn.scalar(select(1)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault", ["target_unverified", "target_membership_revoked", "voter_disabled"]
)
async def test_changed_identity_cannot_create_recovered_authority(approved_recovery, fault):
    service, owner, target_id, voter_id, org_id, request = approved_recovery
    engine = get_enterprise_engine()
    if fault == "target_membership_revoked":
        await EnterpriseIAM(engine).revoke_member(owner, org_id, user_id=target_id)
    else:
        # Negative-only fault injection in disposable PostgreSQL; never mark
        # an identity verified or insert privileged membership for qualification.
        async with engine.raw.begin() as conn:
            if fault == "target_unverified":
                await conn.execute(
                    update(web_users)
                    .where(web_users.c.id == target_id)
                    .values(verification_status="UNVERIFIED", email_verified_at=None)
                )
            else:
                await conn.execute(
                    update(web_users).where(web_users.c.id == voter_id).values(disabled=1)
                )
    before = await recovery_snapshot(engine, org_id)
    with pytest.raises(EnterpriseError) as error:
        await service.execute_recovery_request(
            owner,
            org_id=org_id,
            request_id=request["request_id"],
            action_digest=request["action_digest"],
        )
    assert error.value.code == (
        "QUORUM_NOT_MET" if fault == "voter_disabled" else "UNAUTHORIZED_BOOTSTRAP_CALLER"
    )
    assert await recovery_snapshot(engine, org_id) == before
