"""End-to-end Heart authority resolution from persisted tenant state."""

from __future__ import annotations

import pytest

from responsibleai.db import (
    AuthorityPassportRepository,
    ConsentProofRepository,
    DelegationRepository,
    IntentContractRepository,
    OrgAuthorityCeilingRepository,
    PurposeBindingRepository,
    RootAuthorityRepository,
    create_engine,
)
from responsibleai.governance.authority_passport import build_authority_passport_from_ceiling
from responsibleai.governance.authority_resolver import (
    AuthorityResolutionError,
    AuthorityResolver,
)
from responsibleai.governance.ceiling import OrgAuthorityCeiling
from responsibleai.governance.consent_proof import ConsentMethod, build_consent_proof
from responsibleai.governance.intent import build_intent_contract
from responsibleai.governance.models import IdentityContext
from responsibleai.governance.purpose_binding import build_purpose_binding
from responsibleai.governance.root_authority import RootType, build_root_authority_record


@pytest.fixture()
async def resolved_state():
    engine = create_engine(":memory:")
    await engine.init()
    roots = RootAuthorityRepository(engine)
    consents = ConsentProofRepository(engine)
    bindings = PurposeBindingRepository(engine)
    intents = IntentContractRepository(engine)
    passports = AuthorityPassportRepository(engine)
    delegations = DelegationRepository(engine)
    ceilings = OrgAuthorityCeilingRepository(engine)
    resolver = AuthorityResolver(
        roots=roots,
        consents=consents,
        bindings=bindings,
        intents=intents,
        passports=passports,
        delegations=delegations,
        ceilings=ceilings,
    )
    identity = IdentityContext(identity_id="key-1", kind="api_key", org_id="org-1")
    root = build_root_authority_record(
        identity.identity_id,
        RootType.ORGANIZATION,
        "org-repository",
        "api-key-hash",
        organization_id="org-1",
    )
    consent = build_consent_proof(
        identity.identity_id,
        root.root_id,
        identity.identity_id,
        "Use approved governance tools",
        "govern models",
        ConsentMethod.API_AUTHENTICATED_REQUEST,
        evidence_refs=("request-1",),
    )
    intent = build_intent_contract(
        "org-1",
        identity.identity_id,
        "govern models",
        allowed_action_types=["rai_health"],
    )
    binding = build_purpose_binding("govern models", intent.contract_id, consent.consent_id)
    ceiling = OrgAuthorityCeiling(org_id="org-1", allowed_action_types=["rai_health"])
    passport = build_authority_passport_from_ceiling(ceiling, identity.identity_id)

    await roots.issue("org-1", root)
    await consents.issue("org-1", consent)
    await intents.declare(intent)
    await bindings.bind("org-1", identity.identity_id, binding)
    await ceilings.set(ceiling)
    await passports.issue(passport)

    yield resolver, identity, consents, consent
    await engine.close()


async def test_resolves_a_usable_heart_derived_grant(resolved_state) -> None:
    resolver, identity, _consents, _consent = resolved_state
    grant = await resolver.resolve(
        identity,
        action_type="rai_health",
        target="rai_health",
        purpose="govern models",
    )

    assert grant.is_usable
    assert grant.effective_authority.action_types == frozenset({"rai_health"})
    assert grant.root_reference is not None
    assert grant.consent_reference is not None


async def test_missing_request_purpose_uses_persisted_bound_intent(resolved_state) -> None:
    resolver, identity, _consents, _consent = resolved_state
    grant = await resolver.resolve(
        identity,
        action_type="rai_health",
        target="rai_health",
        purpose=None,
    )
    assert grant.requested_purpose == "govern models"


async def test_conflicting_request_purpose_fails_closed(resolved_state) -> None:
    resolver, identity, _consents, _consent = resolved_state
    with pytest.raises(AuthorityResolutionError, match="PURPOSE_INTENT_MISMATCH"):
        await resolver.resolve(
            identity,
            action_type="rai_health",
            target="rai_health",
            purpose="different purpose",
        )


async def test_revoked_consent_triggers_heart_veto(resolved_state) -> None:
    resolver, identity, consents, consent = resolved_state
    await consents.revoke("org-1", consent.consent_id, revoked_by="admin-1")

    with pytest.raises(AuthorityResolutionError, match="HEART_VETO"):
        await resolver.resolve(
            identity,
            action_type="rai_health",
            target="rai_health",
            purpose="govern models",
        )


async def test_identity_from_another_tenant_cannot_resolve_state(resolved_state) -> None:
    resolver, _identity, _consents, _consent = resolved_state
    other = IdentityContext(identity_id="key-1", kind="api_key", org_id="org-2")
    with pytest.raises(AuthorityResolutionError, match="ROOT_NOT_FOUND"):
        await resolver.resolve(
            other,
            action_type="rai_health",
            target="rai_health",
            purpose="govern models",
        )
