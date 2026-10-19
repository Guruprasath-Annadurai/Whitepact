# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""A2 identity binding receipts, with explicit non-authoritative import controls.

Pending directory imports below carry no root, consent, verified identifier or
privileged session. Their promotion is component qualification, not an invented
customer import API. Verified email proves mailbox control, not legal identity.
"""

import base64
import json
import uuid
from contextlib import asynccontextmanager
from dataclasses import replace

import pytest
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key
from sqlalchemy import func, select, update

from responsibleai.db.engine import (
    authority_step_up_challenges,
    create_engine,
    governance_root_authority_records,
    trust_fabric_bootstrap_records,
    trust_fabric_identifiers,
    trust_fabric_principals,
    web_users,
)
from responsibleai.db.org_authority_ceiling_repository import OrgAuthorityCeilingRepository
from responsibleai.db.policy_repository import PolicyRepository
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.authority.service import CustomerAuthorityService
from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.enterprise.security.policy import SensitiveAction
from responsibleai.enterprise.security.service import IdentitySecurityService
from responsibleai.enterprise.security.webauthn import b64url_decode
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.governance.ceiling import OrgAuthorityCeiling
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import PolicyRule
from responsibleai.rbac.models import Role
from responsibleai.trust_fabric.directory import PrincipalDirectory, normalize_identifier
from responsibleai.trust_fabric.enums import IdentifierType, PrincipalType
from tests.test_sovereign_authority import owner as owner
from tests.test_sovereign_authority import root
from tests.webauthn_fakes import assertion_blob, registration_blob


@asynccontextmanager
async def signed_owner(email):
    """Register, token-verify, enroll and authenticate; never seed session assurance."""
    engine = create_engine(":memory:")
    await engine.init()
    try:
        web = WebIdentityRepository(engine)
        user, verification = await web.register("IDNA owner", email, "Valid-Password42!")
        assert await web.verify_email(verification)
        organization = await EnterpriseIAM(engine).create_workspace(
            actor_user_id=user, name="IDNA", slug=f"idna-{uuid.uuid4().hex}", kind="ORGANIZATION"
        )
        org = organization["id"] if isinstance(organization, dict) else organization.id
        identity = IdentitySecurityService(engine, origin="http://localhost", rp_id="localhost")
        token, _ = await web.create_session(user, org_id=org)
        _, _, password = await identity.load_session(token)
        key = generate_private_key(SECP256R1())
        challenge = await identity.begin_webauthn(
            user_id=user, session_id=password.session_id, ceremony="register", org_id=org
        )
        client, auth, credential, _ = registration_blob(
            rp_id="localhost",
            origin="http://localhost",
            challenge=b64url_decode(challenge["challenge"]),
            private_key=key,
        )
        grant = await identity.issue_step_up(password, SensitiveAction.ADD_PASSKEY, org_id=org)
        await identity.finish_passkey_registration(
            user_id=user,
            session=password,
            client_data_b64=client,
            authenticator_data_b64=auth,
            grant=grant,
        )
        challenge = await identity.begin_webauthn(
            user_id=None, session_id=None, ceremony="authenticate"
        )
        client, auth, signature = assertion_blob(
            rp_id="localhost",
            origin="http://localhost",
            challenge=b64url_decode(challenge["challenge"]),
            private_key=key,
        )
        token, csrf, session = await identity.authenticate_passkey(
            client_data_b64=client,
            authenticator_data_b64=auth,
            signature_b64=signature,
            credential_id=credential,
            org_id=org,
        )
        actor = Actor("human", user, user, org, Role.OWNER, "ACTIVE")
        actor = replace(actor, session_id=session.session_id)
        yield engine, identity, actor, password, session, key, credential, token, csrf
    finally:
        await engine.close()


async def pending_import(engine, actor):
    """Import only a pending identity matching the existing registered web owner."""
    async with engine.raw.begin() as conn:
        await conn.execute(
            trust_fabric_principals.insert().values(
                id=actor.user_id,
                org_id=actor.org_id,
                principal_type="HUMAN",
                display_name="Pending imported identity",
                lifecycle_state="PENDING_VERIFICATION",
                created_at="2026-01-01T00:00:00+00:00",
                updated_at="2026-01-01T00:00:00+00:00",
                metadata_json="{}",
            )
        )


async def assert_no_root(engine, org):
    async with engine.raw.connect() as conn:
        assert (
            await conn.scalar(
                select(func.count())
                .select_from(governance_root_authority_records)
                .where(governance_root_authority_records.c.organization_id == org)
            )
            == 0
        )


@pytest.mark.asyncio
async def test_pending_import_and_unverified_identifier_promote_only_after_signed_a2(owner):
    engine, _, actor, *_ = owner
    await pending_import(engine, actor)
    async with engine.raw.connect() as conn:
        account_before = (
            await conn.execute(select(web_users).where(web_users.c.id == actor.user_id))
        ).one()
        email = account_before.email
    directory = PrincipalDirectory(engine)
    imported = await directory.attach_identifier(
        principal_id=actor.user_id,
        org_id=actor.org_id,
        identifier_type=IdentifierType.EMAIL,
        value=email,
    )
    assert imported.verification_state.value == "UNVERIFIED"
    await assert_no_root(engine, actor.org_id)
    await root(owner)
    async with engine.raw.connect() as conn:
        principal = (
            await conn.execute(
                select(trust_fabric_principals).where(trust_fabric_principals.c.id == actor.user_id)
            )
        ).one()
        identifier = (
            await conn.execute(
                select(trust_fabric_identifiers).where(trust_fabric_identifiers.c.id == imported.id)
            )
        ).one()
        account = (
            await conn.execute(select(web_users).where(web_users.c.id == actor.user_id))
        ).one()
        assert principal.lifecycle_state == "ACTIVE"
        assert identifier.principal_id == actor.user_id
        assert identifier.verification_state == "VERIFIED"
        assert identifier.verified_at == account.email_verified_at
        assert account.email_verified_at is not None
        # Mailbox verification is persisted separately from the legal-identity
        # label. Root enrollment must not upgrade that independent assurance.
        assert account.verification_status == account_before.verification_status
        assert account.verification_status != "IDENTITY_VERIFIED"


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["REVOKED", "SUSPENDED", "DISABLED", "DELETED"])
async def test_revoked_pending_import_cannot_be_resurrected_by_prepared_ceremony(owner, state):
    engine, _, actor, *_ = owner
    await pending_import(engine, actor)
    service, actor, parameters = await root(owner, prepare_only=True)
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(trust_fabric_principals)
            .where(trust_fabric_principals.c.id == actor.user_id)
            .values(lifecycle_state=state)
        )
    with pytest.raises(EnterpriseError):
        await service.complete_root_bootstrap(actor, **parameters)
    with pytest.raises(EnterpriseError):
        await service.initiate_root_bootstrap(actor, org_id=actor.org_id)
    await assert_no_root(engine, actor.org_id)
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
                select(trust_fabric_bootstrap_records.c.consumed_at).where(
                    trust_fabric_bootstrap_records.c.nonce == parameters["nonce"]
                )
            )
            is None
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("collision", [False, True])
async def test_idna_verified_owner_binding_and_same_tenant_collision(collision):
    email = f"idna-{uuid.uuid4().hex}@bücher.example"
    canonical = email.split("@")[0] + "@xn--bcher-kva.example"
    async with signed_owner(email) as identity_owner:
        engine, _, actor, *_ = identity_owner
        service, actor, parameters = await root(identity_owner, prepare_only=True)
        if collision:
            directory = PrincipalDirectory(engine)
            other = await directory.create_principal(
                org_id=actor.org_id,
                principal_type=PrincipalType.HUMAN,
                display_name="Unverified conflicting import",
            )
            imported = await directory.attach_identifier(
                principal_id=other.id,
                org_id=actor.org_id,
                identifier_type=IdentifierType.EMAIL,
                value=canonical,
            )
            with pytest.raises(EnterpriseError):
                await service.complete_root_bootstrap(actor, **parameters)
            await assert_no_root(engine, actor.org_id)
            async with engine.raw.connect() as conn:
                identifier = (
                    await conn.execute(
                        select(trust_fabric_identifiers).where(
                            trust_fabric_identifiers.c.id == imported.id
                        )
                    )
                ).one()
                assert identifier.principal_id == other.id
                assert identifier.verification_state == "UNVERIFIED"
                assert (
                    await conn.scalar(
                        select(func.count())
                        .select_from(trust_fabric_principals)
                        .where(trust_fabric_principals.c.id == actor.user_id)
                    )
                    == 0
                )
                assert (
                    await conn.scalar(
                        select(trust_fabric_bootstrap_records.c.consumed_at).where(
                            trust_fabric_bootstrap_records.c.nonce == parameters["nonce"]
                        )
                    )
                    is None
                )
        else:
            await service.complete_root_bootstrap(actor, **parameters)
            async with engine.raw.connect() as conn:
                identifier = (
                    await conn.execute(
                        select(trust_fabric_identifiers).where(
                            trust_fabric_identifiers.c.principal_id == actor.user_id
                        )
                    )
                ).one()
                assert identifier.normalized_value == canonical
                assert identifier.verification_state == "VERIFIED"
                assert identifier.org_id == actor.org_id
        assert normalize_identifier(IdentifierType.EMAIL, email) == canonical


@pytest.mark.asyncio
@pytest.mark.parametrize("binding", ["foreign_tenant", "revoked"])
async def test_unverified_foreign_or_revoked_binding_does_not_transfer_authority(owner, binding):
    engine, _, actor, *_ = owner
    async with engine.raw.connect() as conn:
        email = await conn.scalar(select(web_users.c.email).where(web_users.c.id == actor.user_id))
    binding_org = actor.org_id
    if binding == "foreign_tenant":
        organization = await EnterpriseIAM(engine).create_workspace(
            actor_user_id=actor.user_id,
            name="Separate tenant",
            slug=f"separate-{uuid.uuid4().hex}",
            kind="ORGANIZATION",
        )
        binding_org = organization["id"] if isinstance(organization, dict) else organization.id
    directory = PrincipalDirectory(engine)
    other = await directory.create_principal(
        org_id=binding_org, principal_type=PrincipalType.HUMAN, display_name="Unverified import"
    )
    imported = await directory.attach_identifier(
        principal_id=other.id,
        org_id=binding_org,
        identifier_type=IdentifierType.EMAIL,
        value=email,
    )
    if binding == "revoked":
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(trust_fabric_identifiers)
                .where(trust_fabric_identifiers.c.id == imported.id)
                .values(revoked_at="2026-01-01T00:00:00+00:00")
            )
    await root(owner)
    async with engine.raw.connect() as conn:
        original = (
            await conn.execute(
                select(trust_fabric_identifiers).where(trust_fabric_identifiers.c.id == imported.id)
            )
        ).one()
        assert original.verification_state == "UNVERIFIED"
        assert original.principal_id == other.id
        assert original.org_id == binding_org
        current = (
            await conn.execute(
                select(trust_fabric_identifiers).where(
                    trust_fabric_identifiers.c.principal_id == actor.user_id,
                    trust_fabric_identifiers.c.org_id == actor.org_id,
                    trust_fabric_identifiers.c.revoked_at.is_(None),
                )
            )
        ).one()
        assert current.id != original.id
        assert current.verification_state == "VERIFIED"
        assert (
            await conn.scalar(
                select(func.count())
                .select_from(governance_root_authority_records)
                .where(governance_root_authority_records.c.subject_id == other.id)
            )
            == 0
        )
        assert (
            await conn.scalar(
                select(trust_fabric_principals.c.lifecycle_state).where(
                    trust_fabric_principals.c.id == other.id
                )
            )
            == "PENDING_VERIFICATION"
        )


@pytest.mark.asyncio
async def test_revoked_root_can_be_reestablished_only_by_a_fresh_signed_ceremony(owner):
    engine, _, actor, _, _, key, *_ = owner
    await root(owner)
    service = CustomerAuthorityService(engine)
    previous = await service.get_authority_status(actor, org_id=actor.org_id)
    with pytest.raises(EnterpriseError):
        await service.initiate_root_bootstrap(actor, org_id=actor.org_id)
    await service.revoke_root_authority(
        actor,
        org_id=actor.org_id,
        root_id=previous["root_authority"]["root_id"],
        reason="Explicitly replace customer-controlled key",
    )
    service, actor, parameters = await root(owner, prepare_only=True)
    assertion = parameters["webauthn_assertion"]
    encoded = assertion["client_data_json"]
    payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    async with engine.raw.connect() as conn:
        challenge = (
            await conn.execute(
                select(authority_step_up_challenges).where(
                    authority_step_up_challenges.c.raw_challenge_b64 == payload["challenge"]
                )
            )
        ).one()
    client, auth, signature = assertion_blob(
        rp_id=challenge.rp_id,
        origin=challenge.origin,
        challenge=b64url_decode(payload["challenge"]),
        private_key=key,
        sign_count=3,
    )
    assertion.update(client_data_json=client, authenticator_data=auth, signature=signature)
    await service.complete_root_bootstrap(actor, **parameters)
    current = await service.get_authority_status(actor, org_id=actor.org_id)
    assert current["has_active_authority"] is True
    assert current["root_authority"]["root_id"] != previous["root_authority"]["root_id"]
    assert current["revocation_epoch"] > previous["revocation_epoch"]
    async with engine.raw.connect() as conn:
        rows = (
            await conn.execute(
                select(governance_root_authority_records).where(
                    governance_root_authority_records.c.organization_id == actor.org_id
                )
            )
        ).all()
        assert len(rows) == 2
        assert sum(row.revoked_at is None for row in rows) == 1
        identifiers = (
            await conn.execute(
                select(trust_fabric_identifiers).where(
                    trust_fabric_identifiers.c.principal_id == actor.user_id
                )
            )
        ).all()
        assert len(identifiers) == 1
        assert identifiers[0].verification_state == "VERIFIED"


@pytest.mark.asyncio
async def test_capabilities_require_real_consent_and_obey_persisted_restrictions(owner):
    """Policy/ceiling repository component receipt; not a customer HTTP mutation receipt."""
    engine, _, actor, *_ = owner
    service = CustomerAuthorityService(engine)
    agent = await service.register_agent(actor, org_id=actor.org_id, name="capability contract")
    agent_id = agent["agent_id"]
    pending = await service.list_capabilities(actor, org_id=actor.org_id, agent_id=agent_id)
    assert len(pending) == 1 and pending[0]["status"] == "PENDING_DELEGATION"
    assert pending[0]["allowed_targets"] == []
    await root(owner)
    await service.delegate_to_agent(
        actor,
        org_id=actor.org_id,
        agent_id=agent_id,
        granted_action_types=["rai_policy_check"],
        allowed_targets=["rai_policy_check"],
        purpose="Customer explicitly authorized harmless local policy checks",
    )

    async def capability():
        rows = await service.list_capabilities(actor, org_id=actor.org_id, agent_id=agent_id)
        assert len(rows) == 1
        assert rows[0]["authority_enforced"] is True
        assert rows[0]["agent_id"] == agent_id
        return rows[0]

    authorized = await capability()
    assert authorized["status"] == "AUTHORIZED"
    assert authorized["allowed_targets"] == ["rai_policy_check"]
    ceilings = OrgAuthorityCeilingRepository(engine)
    await ceilings.set(
        OrgAuthorityCeiling(org_id=actor.org_id, allowed_action_types=["unrelated_action"])
    )
    denied = await capability()
    assert denied["status"] == "POLICY_DENIED" and denied["allowed_targets"] == []
    await ceilings.set(
        OrgAuthorityCeiling(org_id=actor.org_id, allowed_targets=["unrelated_target"])
    )
    denied = await capability()
    assert denied["status"] == "POLICY_DENIED" and denied["allowed_targets"] == []
    await ceilings.set(OrgAuthorityCeiling(org_id=actor.org_id, denied_targets=["rai_*"]))
    denied = await capability()
    assert denied["status"] == "POLICY_DENIED" and denied["allowed_targets"] == []
    await ceilings.set(
        OrgAuthorityCeiling(
            org_id=actor.org_id,
            allowed_action_types=["rai_policy_check"],
            allowed_targets=["rai_*"],
            require_approval_for=frozenset({"rai_policy_check"}),
        )
    )
    approved = await capability()
    assert approved["status"] == "AUTHORIZED" and approved["requires_approval"] is True
    await ceilings.set(OrgAuthorityCeiling(org_id=actor.org_id))
    assert (await capability())["requires_approval"] is False
    policies = PolicyRepository(engine)
    for effect, actions, targets, status, approval in [
        (GovernanceDecision.DENY, frozenset({"other_action"}), None, "AUTHORIZED", False),
        (
            GovernanceDecision.REQUIRE_APPROVAL,
            None,
            frozenset({"other_target"}),
            "AUTHORIZED",
            False,
        ),
        (GovernanceDecision.REQUIRE_APPROVAL, None, frozenset({"rai_*"}), "AUTHORIZED", True),
        (GovernanceDecision.DENY, None, frozenset({"rai_*"}), "POLICY_DENIED", True),
        (GovernanceDecision.DENY, None, None, "POLICY_DENIED", True),
    ]:
        rule = PolicyRule(
            rule_id=f"contract-{uuid.uuid4().hex}",
            reason_code="EXPLICIT_CUSTOMER_RESTRICTION",
            effect=effect,
            action_types=actions,
            targets=targets,
        )
        await policies.add_rule(actor.org_id, rule)
        actual = await capability()
        assert actual["status"] == status
        assert actual["requires_approval"] is approval
        if status == "POLICY_DENIED":
            assert actual["allowed_targets"] == []
        await policies.remove_rule(actor.org_id, rule.rule_id)
    await service.disable_agent(actor, org_id=actor.org_id, agent_id=agent_id)
    assert (await capability())["status"] == "DISABLED"
