# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Authentication must never manufacture runtime authority."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from responsibleai.db.consent_proof_repository import ConsentProofRepository
from responsibleai.db.delegation_repository import DelegationRepository
from responsibleai.db.engine import create_engine, governance_consent_proofs, organizations
from responsibleai.db.root_authority_repository import RootAuthorityRepository
from responsibleai.governance.authority_resolver import AuthorityDenied, AuthorityResolver
from responsibleai.governance.consent_proof import ConsentMethod, build_consent_proof
from responsibleai.governance.context import GovernanceContext
from responsibleai.governance.models import ActionRequest, AgentContext, IdentityContext
from responsibleai.governance.root_authority import RootType, build_root_authority_record
from responsibleai.rbac.models import OrgContext, Role


@pytest.fixture
async def governed():
    engine = create_engine(":memory:")
    await engine.init()
    async with engine.raw.begin() as conn:
        await conn.execute(
            organizations.insert().values(id="acme", name="ACME", slug="acme", created_at="now")
        )
    roots = RootAuthorityRepository(engine)
    consents = ConsentProofRepository(engine)
    delegations = DelegationRepository(engine)
    auth = OrgContext(key_id="worker", role=Role.ADMIN, org_id="acme")
    action = ActionRequest(
        agent=AgentContext(identity=IdentityContext.from_org_context(auth), agent_id="worker"),
        action_type="read",
        target="invoice",
        purpose="reconcile",
    )
    context = GovernanceContext.from_authenticated(auth, action, authentication_method="api_key")
    root = build_root_authority_record(
        "owner",
        RootType.HUMAN,
        "customer",
        "reviewed-document",
        organization_id="acme",
        evidence_refs=("customer-proof-1",),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    await roots.create(root)
    consent = build_consent_proof(
        "owner",
        root.root_id,
        "worker",
        "invoice read",
        "reconcile",
        ConsentMethod.SIGNED_DOCUMENT,
        allowed_action_types=("read",),
        allowed_targets=("invoice",),
        evidence_refs=("customer-consent-1",),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    await consents.create(consent, organization_id="acme")
    await delegations.grant(
        "acme",
        "worker",
        granted_action_types=frozenset({"read"}),
        constraints={"allowed_targets": ["invoice"]},
        purpose="reconcile",
        granted_by="owner",
    )
    yield engine, roots, consents, delegations, context, root, consent
    await engine.close()


async def test_explicit_grant_resolves(governed):
    engine, roots, consents, delegations, context, root, consent = governed
    resolved = await AuthorityResolver(roots, consents, delegations).resolve(context)
    assert resolved.grant.is_usable
    assert resolved.grant.consent_reference == consent.consent_id
    assert resolved.grant.root_reference == root.root_id
    assert resolved.authority.permits("read")
    assert resolved.authority_version


@pytest.mark.parametrize("mutation", ["wrong_org", "wrong_subject", "legacy", "missing_org"])
def test_context_rejects_untrusted_tenant_or_identity(mutation):
    auth = OrgContext(key_id="a", role=Role.ADMIN, org_id="acme")
    action = ActionRequest(
        AgentContext(IdentityContext("a", "api_key", org_id="acme")), "read", "x"
    )
    if mutation == "wrong_org":
        action.agent.organization_id = "other"
    elif mutation == "wrong_subject":
        action.agent.identity.identity_id = "other"
    elif mutation == "legacy":
        auth.is_legacy = True
    else:
        auth.org_id = None
    with pytest.raises(ValueError):
        GovernanceContext.from_authenticated(auth, action, authentication_method="api_key")


@pytest.mark.parametrize(
    "field,value",
    [
        ("allowed_action_types", "[]"),
        ("allowed_targets", "[]"),
        ("purpose", "other"),
        ("grantee_id", "other"),
        ("canonical_digest", "tampered"),
        ("expires_at", "2000-01-01T00:00:00+00:00"),
        ("revoked_at", "2026-01-01T00:00:00+00:00"),
    ],
)
async def test_invalid_consent_never_falls_back(governed, field, value):
    engine, roots, consents, delegations, context, _, consent = governed
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(governance_consent_proofs)
            .where(governance_consent_proofs.c.consent_id == consent.consent_id)
            .values(**{field: value})
        )
    with pytest.raises(AuthorityDenied):
        await AuthorityResolver(roots, consents, delegations).resolve(context)


@pytest.mark.parametrize("purpose", [None, "", "other"])
async def test_missing_or_changed_purpose_denied(governed, purpose):
    _, roots, consents, delegations, context, _, _ = governed
    changed = replace(context, action=replace(context.action, purpose=purpose))
    with pytest.raises(AuthorityDenied):
        await AuthorityResolver(roots, consents, delegations).resolve(changed)


async def test_revoked_root_denied_and_not_reissued(governed):
    _, roots, consents, delegations, context, root, _ = governed
    await roots.revoke(root.root_id, organization_id="acme", revoked_by="owner")
    with pytest.raises(AuthorityDenied):
        await AuthorityResolver(roots, consents, delegations).resolve(context)
    latest = await roots.get_latest_for_subject("owner", organization_id="acme")
    assert latest.root_id == root.root_id
    assert latest.revoked_at is not None


async def test_cross_tenant_repository_access_is_hidden(governed):
    _, roots, consents, _, _, root, consent = governed
    assert await roots.get(root.root_id, organization_id="other") is None
    assert await consents.get(consent.consent_id, organization_id="other") is None


async def test_admin_without_delegation_denied(governed):
    _, roots, consents, delegations, context, _, _ = governed
    await delegations.revoke_branch("acme", "worker", revoked_by="owner", reason="removed")
    with pytest.raises(AuthorityDenied):
        await AuthorityResolver(roots, consents, delegations).resolve(context)


@pytest.mark.parametrize("actions,targets", [((), ("invoice",)), (("read",), ())])
async def test_integrity_valid_but_unscoped_consent_denied(governed, actions, targets):
    _, roots, consents, delegations, context, root, _ = governed
    proof = build_consent_proof(
        "owner", root.root_id, "worker", "no scope", "reconcile",
        ConsentMethod.SIGNED_DOCUMENT, allowed_action_types=actions,
        allowed_targets=targets, evidence_refs=("explicit-empty-grant",),
    )
    await consents.create(proof, organization_id="acme")
    with pytest.raises(AuthorityDenied):
        await AuthorityResolver(roots, consents, delegations).resolve(context)


async def test_expiry_mutation_detected(governed):
    from responsibleai.governance.consent_proof import verify_consent_proof_integrity

    _, _, _, _, _, _, consent = governed
    assert verify_consent_proof_integrity(consent)
    assert not verify_consent_proof_integrity(replace(consent, expires_at=None))
