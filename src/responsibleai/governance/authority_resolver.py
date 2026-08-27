"""Resolve persisted Heart state into the production ``AuthorityGrant``.

This is the fail-closed boundary between authentication and authorization.
It is the only production service permitted to turn persisted Heart inputs
into authority consumed by the existing runtime gateway.
"""

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.db.authority_passport_repository import AuthorityPassportRepository
from responsibleai.db.delegation_repository import DelegationRepository
from responsibleai.db.heart_repository import (
    ConsentProofRepository,
    PurposeBindingRepository,
    RootAuthorityRepository,
)
from responsibleai.db.intent_repository import IntentContractRepository
from responsibleai.db.org_authority_ceiling_repository import OrgAuthorityCeilingRepository
from responsibleai.governance.authority_grant import AuthorityGrant, build_authority_grant
from responsibleai.governance.authority_lattice import (
    AuthorityEnvelope,
    authority_context_to_envelope,
    intersect_envelopes,
)
from responsibleai.governance.authority_passport import PassportStatus, verify_passport
from responsibleai.governance.heart_veto import HeartVetoError, enforce_heart_veto
from responsibleai.governance.models import IdentityContext
from responsibleai.governance.sovereignty_kernel import evaluate as evaluate_sovereignty


@dataclass(frozen=True)
class AuthorityResolutionError(Exception):
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


class AuthorityResolver:
    def __init__(
        self,
        *,
        roots: RootAuthorityRepository,
        consents: ConsentProofRepository,
        bindings: PurposeBindingRepository,
        intents: IntentContractRepository,
        passports: AuthorityPassportRepository,
        delegations: DelegationRepository,
        ceilings: OrgAuthorityCeilingRepository,
    ) -> None:
        self._roots = roots
        self._consents = consents
        self._bindings = bindings
        self._intents = intents
        self._passports = passports
        self._delegations = delegations
        self._ceilings = ceilings

    async def resolve(
        self,
        identity: IdentityContext,
        *,
        action_type: str,
        target: str,
        purpose: str | None,
    ) -> AuthorityGrant:
        org_id = identity.org_id
        if not org_id:
            raise AuthorityResolutionError("TENANT_REQUIRED", "Heart requires an organization")
        root = await self._roots.get_latest_for_subject(org_id, identity.identity_id)
        if root is None:
            raise AuthorityResolutionError("ROOT_NOT_FOUND", "No root authority is registered")
        if root.organization_id != org_id or root.subject_id != identity.identity_id:
            raise AuthorityResolutionError(
                "ROOT_IDENTITY_MISMATCH", "Root authority does not match the authenticated tenant"
            )

        intent = await self._intents.get_active_for_agent(org_id, identity.identity_id)
        if intent is None:
            raise AuthorityResolutionError("INTENT_NOT_FOUND", "No active intent contract exists")
        effective_purpose = purpose or intent.goal
        if purpose is not None and purpose != intent.goal:
            raise AuthorityResolutionError(
                "PURPOSE_INTENT_MISMATCH", "Requested purpose does not match the active intent"
            )

        consent = await self._consents.get_latest_for_grantee(
            org_id, identity.identity_id, effective_purpose
        )
        if consent is None:
            raise AuthorityResolutionError(
                "CONSENT_NOT_FOUND", "No matching consent proof is registered"
            )
        if consent.consenting_root_id != root.root_id:
            raise AuthorityResolutionError(
                "CONSENT_ROOT_MISMATCH", "Consent is not bound to the active root authority"
            )

        binding = await self._bindings.get_for_refs(
            org_id, identity.identity_id, intent.contract_id, consent.consent_id
        )
        if binding is None:
            raise AuthorityResolutionError(
                "PURPOSE_BINDING_NOT_FOUND", "Consent is not bound to the active intent"
            )

        passport = await self._passports.get_active_for_principal(org_id, identity.identity_id)
        if passport is None:
            raise AuthorityResolutionError(
                "AUTHORITY_NOT_FOUND", "No active authority passport exists"
            )

        delegation = None
        ceiling = None
        if passport.source == "delegation":
            delegation = await self._delegations.get_for_org(org_id, passport.source_id)
        elif passport.source == "org_ceiling":
            ceiling = await self._ceilings.get(org_id)
        verification = verify_passport(passport, ceiling=ceiling, delegation=delegation)
        if verification.status != PassportStatus.VALID:
            raise AuthorityResolutionError(
                "AUTHORITY_PASSPORT_INVALID",
                verification.detail or verification.status.value,
            )

        chain = await self._roots.load_chain(org_id, root)
        legitimacy = evaluate_sovereignty(
            org_id,
            identity.identity_id,
            root=root,
            root_resolver=lambda root_id: chain.get(root_id),
            consent=consent,
            intent=intent,
            purpose_binding=binding,
            delegation=delegation,
            requested_action_types=frozenset({action_type}),
        )
        try:
            enforce_heart_veto(legitimacy.heart_veto)
        except HeartVetoError as exc:
            raise AuthorityResolutionError("HEART_VETO", str(exc)) from exc

        passport_authority = authority_context_to_envelope(passport.to_authority_context())
        intent_authority = AuthorityEnvelope(
            action_types=(
                frozenset(intent.allowed_action_types)
                if intent.allowed_action_types is not None
                else None
            ),
            targets=(
                frozenset(intent.allowed_targets) if intent.allowed_targets is not None else None
            ),
            denied_targets=(
                frozenset(intent.denied_targets) if intent.denied_targets is not None else None
            ),
            max_value=intent.max_value_usd,
        )
        effective_authority = intersect_envelopes(passport_authority, intent_authority)
        return build_authority_grant(
            org_id,
            identity.identity_id,
            identity.identity_id,
            action_type,
            target,
            effective_authority,
            legitimacy,
            requested_purpose=effective_purpose,
            root_reference=root.root_id,
            consent_reference=consent.consent_id,
            delegation_reference=delegation.delegation_id if delegation else None,
        )
