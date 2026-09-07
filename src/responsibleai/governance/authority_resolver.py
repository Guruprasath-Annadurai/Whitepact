# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Resolve explicit customer authority; authentication never manufactures a root.

Reconciles PR55's persistence/Heart composition with mandatory tenant, consent,
purpose and delegation checks. Missing data is a denial, not an optional check.
Record digests detect corruption, not a malicious administrator recomputing them.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from responsibleai.db.consent_proof_repository import ConsentProofRepository
from responsibleai.db.delegation_repository import DelegationRepository
from responsibleai.db.root_authority_repository import RootAuthorityRepository
from responsibleai.governance.authority_grant import AuthorityGrant, build_authority_grant
from responsibleai.governance.authority_lattice import authority_context_to_envelope
from responsibleai.governance.consent_proof import verify_consent_proof_integrity
from responsibleai.governance.context import GovernanceContext
from responsibleai.governance.intent import IntentContract
from responsibleai.governance.models import AuthorityContext, validate_attenuation
from responsibleai.governance.purpose_binding import build_purpose_binding
from responsibleai.governance.root_authority import RootAuthorityRecord, compute_root_digest
from responsibleai.governance.sovereignty_kernel import evaluate


class AuthorityDenied(Exception):  # noqa: N818 - internal denial verdict, translated by transports
    """Use a generic denial at transports; retain a safe reason code internally."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__("Authority verification failed")


@dataclass(frozen=True)
class ResolvedAuthority:
    grant: AuthorityGrant
    authority: AuthorityContext
    authority_version: str


def _root_integrity(root: RootAuthorityRecord) -> bool:
    return root.canonical_digest == compute_root_digest(
        root.root_id,
        root.root_type,
        root.subject_id,
        root.organization_id,
        root.issuer,
        root.verification_method,
        root.authority_source,
        root.issued_at,
        root.not_before,
        root.expires_at,
        root.evidence_refs,
        root.jurisdiction,
    )


class AuthorityResolver:
    def __init__(
        self,
        roots: RootAuthorityRepository,
        consents: ConsentProofRepository,
        delegations: DelegationRepository,
    ):
        self.roots = roots
        self.consents = consents
        self.delegations = delegations

    async def resolve(self, context: GovernanceContext) -> ResolvedAuthority:
        try:
            context.validate_binding()
        except ValueError as exc:
            raise AuthorityDenied("CONTEXT_MISMATCH") from exc
        action = context.action
        org = context.organization_id
        principal = context.subject_id
        if not action.purpose or not action.purpose.strip():
            raise AuthorityDenied("PURPOSE_REQUIRED")
        consent = await self.consents.get_latest_for_grantee(principal, organization_id=org)
        if (
            consent is None
            or not verify_consent_proof_integrity(consent)
            or not consent.is_temporally_valid()
            or not consent.evidence_refs
        ):
            raise AuthorityDenied("CONSENT_INVALID")
        if (
            consent.grantee_id != principal
            or action.action_type not in consent.allowed_action_types
            or action.target not in consent.allowed_targets
            or action.purpose != consent.purpose
        ):
            raise AuthorityDenied("CONSENT_SCOPE_MISMATCH")

        root = await self.roots.get(consent.consenting_root_id, organization_id=org)
        if root is None or root.subject_id != consent.subject_id:
            raise AuthorityDenied("ROOT_MISSING_OR_MISMATCHED")
        roots: dict[str, RootAuthorityRecord] = {}
        current = root
        for _ in range(32):
            if (
                current.root_id in roots
                or current.organization_id != org
                or not _root_integrity(current)
                or not current.is_temporally_valid()
                or not current.evidence_refs
            ):
                raise AuthorityDenied("ROOT_CHAIN_INVALID")
            roots[current.root_id] = current
            if current.is_terminal():
                break
            source = await self.roots.get(current.authority_source or "", organization_id=org)
            if source is None:
                raise AuthorityDenied("ROOT_CHAIN_INCOMPLETE")
            current = source
        else:
            raise AuthorityDenied("ROOT_CHAIN_TOO_DEEP")

        # Load latest records, including revocation, not an older active fallback.
        chain = []
        seen: set[str] = set()
        subject: str | None = principal
        for _ in range(32):
            if subject is None:
                break
            if subject in seen:
                raise AuthorityDenied("DELEGATION_CYCLE")
            seen.add(subject)
            record = await self.delegations.get_latest_delegation(org, subject)
            if (
                record is None
                or not record.is_active()
                or record.org_id != org
                or record.to_identity_id != subject
                or record.purpose != action.purpose
            ):
                raise AuthorityDenied("DELEGATION_INVALID")
            chain.append(record)
            subject = record.from_identity_id
        else:
            raise AuthorityDenied("DELEGATION_CHAIN_TOO_DEEP")
        if not chain or chain[-1].granted_by != current.subject_id:
            raise AuthorityDenied("DELEGATION_ROOT_MISMATCH")
        for child, parent in zip(chain, chain[1:], strict=False):
            if validate_attenuation(parent.to_authority_context(), child.to_authority_context()):
                raise AuthorityDenied("DELEGATION_ESCALATION")
        authority = chain[0].to_authority_context()
        if not authority.permits(action.action_type) or authority.constraint_violation(action):
            raise AuthorityDenied("AUTHORITY_SCOPE_MISMATCH")
        intent = IntentContract(
            organization_id=org,
            agent_id=action.agent.agent_id,
            goal=action.purpose,
            allowed_targets=consent.allowed_targets,
            allowed_action_types=consent.allowed_action_types,
            expires_at=consent.expires_at,
        )
        binding = build_purpose_binding(action.purpose, intent.contract_id, consent.consent_id)

        def resolve_root(root_id: str) -> RootAuthorityRecord | None:
            return roots.get(root_id)

        legitimacy = evaluate(
            org,
            principal,
            root=root,
            root_resolver=resolve_root,
            consent=consent,
            intent=intent,
            purpose_binding=binding,
            delegation=chain[0],
            requested_action_types=frozenset({action.action_type}),
        )
        if not legitimacy.is_legitimate:
            raise AuthorityDenied("HEART_VETO")
        expirations = [r.expires_at for r in roots.values() if r.expires_at is not None]
        expirations += [d.expires_at for d in chain if d.expires_at is not None]
        if consent.expires_at is not None:
            expirations.append(consent.expires_at)
        ttl = min([30.0] + [(expiry - datetime.now(UTC)).total_seconds() for expiry in expirations])
        if ttl <= 0:
            raise AuthorityDenied("AUTHORITY_EXPIRED")
        version_payload = {
            "roots": [r.to_dict() for r in roots.values()],
            "consent": consent.to_dict(),
            "delegations": [
                {
                    "id": d.delegation_id,
                    "from": d.from_identity_id,
                    "to": d.to_identity_id,
                    "org": d.org_id,
                    "actions": sorted(d.granted_action_types),
                    "constraints": d.constraints,
                    "purpose": d.purpose,
                    "approvals": sorted(d.require_approval_for),
                    "granted_by": d.granted_by,
                    "granted_at": d.granted_at.isoformat(),
                    "expires_at": d.expires_at.isoformat() if d.expires_at else None,
                }
                for d in chain
            ],
        }
        version = hashlib.sha256(
            json.dumps(
                version_payload,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        ).hexdigest()
        grant = build_authority_grant(
            org,
            principal,
            action.agent.agent_id,
            action.action_type,
            action.target,
            authority_context_to_envelope(authority),
            legitimacy,
            requested_purpose=action.purpose,
            root_reference=root.root_id,
            consent_reference=consent.consent_id,
            delegation_reference=chain[0].delegation_id,
            ttl_seconds=ttl,
        )
        return ResolvedAuthority(grant, authority, version)
