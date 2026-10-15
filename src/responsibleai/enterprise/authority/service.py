# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enterprise Customer Authority & Trust Fabric Bridge Service.

Constitutional Invariants:
1. Registration does NOT equal authority: An organization or agent signup never
   manufactures runtime execution authority.
2. Legitimate Customer Root: Authority originates exclusively from an authenticated,
   verified customer owner via a replay-resistant, atomic bootstrap ceremony.
3. Explicit Scoped Consent: The customer explicitly binds permitted action types,
   target resource patterns, and bounded purpose before any agent can act.
4. Single Authority Kernel: Bridges Trust Fabric root ownership into canonical
   governance root records (governance_root_authority_records & governance_consent_proofs)
   under a single shared revocation epoch.
5. Strict Multi-Tenant Isolation: Cross-tenant operations strictly fail closed.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, select, update

from responsibleai.db.delegation_repository import DelegationRepository
from responsibleai.db.engine import (
    DatabaseEngine,
    governance_consent_proofs,
    governance_delegations,
    governance_root_authority_records,
    trust_fabric_bootstrap_records,
    trust_fabric_principals,
    trust_fabric_trust_roots,
    web_users,
)
from responsibleai.db.revocation_epoch_repository import (
    RevocationEpochRepository,
    bump_epoch_on_connection,
    lock_epoch,
)
from responsibleai.enterprise.audit import EnterpriseAuditLog
from responsibleai.enterprise.authority.errors import (
    agent_not_found,
    assurance_required,
    bootstrap_expired,
    bootstrap_invalid,
    bootstrap_replay,
    consent_invalid,
    root_already_exists,
    root_not_found,
    unauthorized_caller,
)
from responsibleai.enterprise.errors import (
    CROSS_TENANT,
    FORBIDDEN,
    forbidden,
)
from responsibleai.enterprise.service import Actor
from responsibleai.governance.consent_proof import (
    ConsentMethod,
    build_consent_proof,
)
from responsibleai.governance.root_authority import (
    RootType,
    build_root_authority_record,
)
from responsibleai.rbac.models import Role
from responsibleai.trust_fabric.enums import PrincipalState, PrincipalType
from responsibleai.trust_fabric.models import compute_digest


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _now()).isoformat()


class CustomerAuthorityService:
    """Manages legitimate customer root authority, consent, and agent delegation."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine
        self._audit = EnterpriseAuditLog(engine)
        self._delegations = DelegationRepository(engine)
        self._epochs = RevocationEpochRepository(engine)

    def _verify_tenant_and_role(self, actor: Actor, org_id: str, require_owner: bool = False) -> None:
        """Enforce authenticated tenant context and role authority."""
        if actor.org_id != org_id:
            raise forbidden(CROSS_TENANT, "Cross-tenant access strictly forbidden.")
        if require_owner:
            if actor.role != Role.OWNER:
                raise unauthorized_caller("This operation requires verified Organization Owner role.")
        else:
            if actor.role not in {Role.OWNER, Role.ADMIN}:
                raise unauthorized_caller("This operation requires Organization Owner or Admin role.")

    async def initiate_root_bootstrap(
        self,
        actor: Actor,
        *,
        org_id: str,
        ttl_seconds: int = 900,
        require_identity_assurance: bool = False,
    ) -> dict[str, Any]:
        """Initiate a server-generated, replay-resistant bootstrap ceremony.

        Returns a one-time challenge token and nonce bound to the authenticated owner.
        """
        self._verify_tenant_and_role(actor, org_id, require_owner=True)

        if require_identity_assurance:
            async with self._engine.raw.connect() as conn:
                row = (
                    await conn.execute(
                        select(web_users.c.verification_status).where(web_users.c.id == actor.user_id)
                    )
                ).first()
                if not row or row[0] not in {"VERIFIED", "IDENTITY_VERIFIED", "BASIC_VERIFIED"}:
                    raise assurance_required()

        # Check if organization already possesses an active canonical root
        async with self._engine.raw.connect() as conn:
            canon_root = (
                await conn.execute(
                    select(governance_root_authority_records.c.root_id).where(
                        and_(
                            governance_root_authority_records.c.organization_id == org_id,
                            governance_root_authority_records.c.revoked_at.is_(None),
                        )
                    )
                )
            ).first()
            if canon_root:
                raise root_already_exists("Organization already has an active canonical root authority.")

            tf_root = (
                await conn.execute(
                    select(trust_fabric_trust_roots.c.id).where(
                        and_(
                            trust_fabric_trust_roots.c.org_id == org_id,
                            trust_fabric_trust_roots.c.status == "ACTIVE",
                        )
                    )
                )
            ).first()
            if tf_root:
                raise root_already_exists("Organization already has an active Trust Fabric root.")

        token = f"wp_boot_{secrets.token_urlsafe(32)}"
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        nonce = f"wp_nonce_{secrets.token_hex(16)}"
        now_dt = _now()
        expires_at_dt = now_dt + timedelta(seconds=ttl_seconds)
        expires_at = _iso(expires_at_dt)
        rec_id = f"wp_brec_{uuid.uuid4().hex}"

        async with self._engine.raw.begin() as conn:
            existing_rec = (
                await conn.execute(
                    select(trust_fabric_bootstrap_records).where(
                        trust_fabric_bootstrap_records.c.org_id == org_id
                    )
                )
            ).first()

            if existing_rec:
                row = dict(existing_rec._mapping)
                if row["consumed_at"] is not None:
                    # If previously consumed but root was revoked, allow refreshing ceremony
                    # check if active root still exists
                    has_root = (
                        await conn.execute(
                            select(governance_root_authority_records.c.root_id).where(
                                and_(
                                    governance_root_authority_records.c.organization_id == org_id,
                                    governance_root_authority_records.c.revoked_at.is_(None),
                                )
                            )
                        )
                    ).first()
                    if has_root:
                        raise root_already_exists()
                await conn.execute(
                    update(trust_fabric_bootstrap_records)
                    .where(trust_fabric_bootstrap_records.c.org_id == org_id)
                    .values(
                        token_hash=token_hash,
                        nonce=nonce,
                        expires_at=expires_at,
                        consumed_at=None,
                        claimed_by_principal_id=actor.user_id,
                        created_at=_iso(now_dt),
                    )
                )
            else:
                await conn.execute(
                    trust_fabric_bootstrap_records.insert().values(
                        id=rec_id,
                        org_id=org_id,
                        token_hash=token_hash,
                        expires_at=expires_at,
                        consumed_at=None,
                        claimed_by_principal_id=actor.user_id,
                        nonce=nonce,
                        created_at=_iso(now_dt),
                    )
                )

        return {
            "ceremony_id": rec_id,
            "organization_id": org_id,
            "token": token,
            "nonce": nonce,
            "expires_at": expires_at,
            "bound_owner_id": actor.user_id,
        }

    async def complete_root_bootstrap(
        self,
        actor: Actor,
        *,
        org_id: str,
        token: str,
        nonce: str,
        root_public_key: str,
        scope_description: str,
        purpose: str,
        allowed_action_types: list[str],
        allowed_targets: list[str],
        key_algorithm: str = "Ed25519",
        consent_method: str = "CRYPTOGRAPHIC_CEREMONY",
        evidence_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        """Atomically complete root bootstrap ceremony with explicit scoped consent.

        Bridges Trust Fabric into canonical governance root authority and consent proofs.
        """
        self._verify_tenant_and_role(actor, org_id, require_owner=True)

        if not token or not nonce:
            raise bootstrap_invalid("Token and nonce are required.")
        if not scope_description or not scope_description.strip():
            raise consent_invalid("Scope description cannot be empty.")
        if not purpose or not purpose.strip():
            raise consent_invalid("Purpose cannot be empty.")
        if not allowed_action_types:
            raise consent_invalid("Allowed action types list cannot be empty.")
        if not allowed_targets:
            raise consent_invalid("Allowed targets list cannot be empty.")

        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now_dt = _now()
        now_iso = _iso(now_dt)

        async with self._engine.raw.begin() as conn:
            # 1. Lock tenant revocation epoch to serialize concurrent ceremony attempts
            await lock_epoch(conn, org_id)

            # 2. Check no active canonical root already exists (anti-race)
            existing_canon = (
                await conn.execute(
                    select(governance_root_authority_records.c.root_id).where(
                        and_(
                            governance_root_authority_records.c.organization_id == org_id,
                            governance_root_authority_records.c.revoked_at.is_(None),
                        )
                    )
                )
            ).first()
            if existing_canon:
                raise root_already_exists("Concurrent attempt already established root authority.")

            # 3. Verify bootstrap record
            boot_row = (
                await conn.execute(
                    select(trust_fabric_bootstrap_records).where(
                        and_(
                            trust_fabric_bootstrap_records.c.org_id == org_id,
                            trust_fabric_bootstrap_records.c.nonce == nonce,
                        )
                    )
                )
            ).first()
            if not boot_row:
                raise bootstrap_invalid("No matching bootstrap ceremony record for this nonce.")

            rec = dict(boot_row._mapping)

            # Constant-time token hash comparison
            if not secrets.compare_digest(rec["token_hash"], token_hash):
                raise bootstrap_invalid("Bootstrap token does not match.")

            # Anti-replay check
            if rec["consumed_at"] is not None:
                raise bootstrap_replay("Bootstrap ceremony token has already been consumed.")

            # Expiry check
            if now_iso >= rec["expires_at"]:
                raise bootstrap_expired(f"Bootstrap ceremony expired at {rec['expires_at']}.")

            # Principal binding check
            if rec.get("claimed_by_principal_id") and rec["claimed_by_principal_id"] != actor.user_id:
                raise unauthorized_caller(
                    f"Ceremony is bound to principal {rec['claimed_by_principal_id']!r}, "
                    f"cannot be claimed by {actor.user_id!r}."
                )

            # 4. Mark ceremony record consumed (anti-replay)
            await conn.execute(
                update(trust_fabric_bootstrap_records)
                .where(trust_fabric_bootstrap_records.c.id == rec["id"])
                .values(consumed_at=now_iso, claimed_by_principal_id=actor.user_id)
            )

            # 5. Insert or update Trust Fabric Trust Root
            tf_root_id = f"wp_tfroot_{uuid.uuid4().hex}"
            tf_digest = compute_digest(
                {
                    "id": tf_root_id,
                    "org_id": org_id,
                    "root_principal_id": actor.user_id,
                    "root_public_key": root_public_key,
                    "established_at": now_iso,
                    "key_algorithm": key_algorithm,
                }
            )

            existing_tf_root = (
                await conn.execute(
                    select(trust_fabric_trust_roots.c.id).where(
                        trust_fabric_trust_roots.c.org_id == org_id
                    )
                )
            ).first()

            if existing_tf_root:
                await conn.execute(
                    update(trust_fabric_trust_roots)
                    .where(trust_fabric_trust_roots.c.org_id == org_id)
                    .values(
                        root_principal_id=actor.user_id,
                        root_public_key=root_public_key,
                        key_algorithm=key_algorithm,
                        established_at=now_iso,
                        status="ACTIVE",
                        canonical_digest=tf_digest,
                    )
                )
                tf_root_id = existing_tf_root[0]
            else:
                await conn.execute(
                    trust_fabric_trust_roots.insert().values(
                        id=tf_root_id,
                        org_id=org_id,
                        root_principal_id=actor.user_id,
                        root_public_key=root_public_key,
                        key_algorithm=key_algorithm,
                        established_at=now_iso,
                        status="ACTIVE",
                        canonical_digest=tf_digest,
                    )
                )

            # 6. Bridge into Canonical Governance: Root Authority Record
            canon_refs = tuple(evidence_refs or [f"bootstrap_nonce:{nonce}"])
            canon_root_record = build_root_authority_record(
                subject_id=actor.user_id or "",
                root_type=RootType.HUMAN,
                issuer=f"customer:{actor.user_id}",
                verification_method="customer_bootstrap_ceremony",
                organization_id=org_id,
                jurisdiction="enterprise",
                evidence_refs=canon_refs,
                expires_at=now_dt + timedelta(days=365),
            )

            await conn.execute(
                governance_root_authority_records.insert().values(
                    root_id=canon_root_record.root_id,
                    subject_id=canon_root_record.subject_id,
                    root_type=canon_root_record.root_type.value,
                    organization_id=org_id,
                    issuer=canon_root_record.issuer,
                    verification_method=canon_root_record.verification_method,
                    authority_source=None,
                    jurisdiction=canon_root_record.jurisdiction,
                    evidence_refs=json.dumps(list(canon_root_record.evidence_refs)),
                    issued_at=canon_root_record.issued_at.isoformat(),
                    not_before=canon_root_record.not_before.isoformat() if canon_root_record.not_before else None,
                    expires_at=canon_root_record.expires_at.isoformat() if canon_root_record.expires_at else None,
                    revoked_at=None,
                    revoked_by=None,
                    revoke_reason=None,
                    canonical_digest=canon_root_record.canonical_digest,
                )
            )

            # 7. Bridge into Canonical Governance: Explicit Consent Proof
            cm_enum = ConsentMethod.SIGNED_DOCUMENT
            try:
                cm_enum = ConsentMethod(consent_method)
            except ValueError:
                cm_enum = ConsentMethod.SIGNED_DOCUMENT

            consent_record = build_consent_proof(
                subject_id=actor.user_id or "",
                consenting_root_id=canon_root_record.root_id,
                grantee_id=actor.user_id or "",
                scope_description=scope_description,
                purpose=purpose,
                consent_method=cm_enum,
                allowed_action_types=tuple(sorted(allowed_action_types)),
                allowed_targets=tuple(sorted(allowed_targets)),
                evidence_refs=canon_refs,
                expires_at=now_dt + timedelta(days=365),
            )

            await conn.execute(
                governance_consent_proofs.insert().values(
                    consent_id=consent_record.consent_id,
                    organization_id=org_id,
                    subject_id=consent_record.subject_id,
                    consenting_root_id=canon_root_record.root_id,
                    grantee_id=consent_record.grantee_id,
                    scope_description=consent_record.scope_description,
                    purpose=consent_record.purpose,
                    consent_method=consent_record.consent_method.value,
                    allowed_action_types=json.dumps(list(consent_record.allowed_action_types)),
                    allowed_targets=json.dumps(list(consent_record.allowed_targets)),
                    evidence_refs=json.dumps(list(consent_record.evidence_refs)),
                    consented_at=consent_record.consented_at.isoformat(),
                    not_before=consent_record.not_before.isoformat() if consent_record.not_before else None,
                    expires_at=consent_record.expires_at.isoformat() if consent_record.expires_at else None,
                    revoked_at=None,
                    revoked_by=None,
                    revoke_reason=None,
                    canonical_digest=consent_record.canonical_digest,
                )
            )

            # 8. Grant Initial Root Delegation to the Customer Owner
            delegation_id = str(uuid.uuid4())
            await conn.execute(
                governance_delegations.insert().values(
                    id=delegation_id,
                    org_id=org_id,
                    from_identity_id=None,
                    to_identity_id=actor.user_id,
                    granted_action_types=json.dumps(sorted(allowed_action_types)),
                    constraints=json.dumps({"allowed_targets": sorted(allowed_targets)}),
                    require_approval_for=None,
                    purpose=purpose,
                    granted_by=actor.user_id,
                    granted_at=now_iso,
                    expires_at=(now_dt + timedelta(days=365)).isoformat(),
                )
            )

            # 9. Authoritative Revocation Epoch Bump
            new_epoch = await bump_epoch_on_connection(conn, org_id)

            # 10. Durable Audit Evidence
            await self._audit.record(
                action="CUSTOMER_ROOT_AUTHORITY_BOOTSTRAPPED",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                org_id=org_id,
                target_type="root_authority",
                target_id=canon_root_record.root_id,
                result="SUCCESS",
                conn=conn,
                metadata={
                    "tf_root_id": tf_root_id,
                    "consent_id": consent_record.consent_id,
                    "delegation_id": delegation_id,
                    "nonce": nonce,
                    "epoch": new_epoch,
                },
            )

        return {
            "status": "BOOTSTRAPPED",
            "organization_id": org_id,
            "root_id": canon_root_record.root_id,
            "consent_id": consent_record.consent_id,
            "delegation_id": delegation_id,
            "tf_root_id": tf_root_id,
            "subject_id": actor.user_id,
            "epoch": new_epoch,
            "established_at": now_iso,
            "canonical_digest": canon_root_record.canonical_digest,
        }

    async def get_authority_status(self, actor: Actor, *, org_id: str) -> dict[str, Any]:
        """Query the organization's current customer root authority and consent status."""
        self._verify_tenant_and_role(actor, org_id)

        async with self._engine.raw.connect() as conn:
            root_row = (
                await conn.execute(
                    select(governance_root_authority_records)
                    .where(
                        and_(
                            governance_root_authority_records.c.organization_id == org_id,
                            governance_root_authority_records.c.revoked_at.is_(None),
                        )
                    )
                    .order_by(governance_root_authority_records.c.issued_at.desc())
                    .limit(1)
                )
            ).first()

            consent_row = None
            if root_row:
                consent_row = (
                    await conn.execute(
                        select(governance_consent_proofs)
                        .where(
                            and_(
                                governance_consent_proofs.c.organization_id == org_id,
                                governance_consent_proofs.c.consenting_root_id == root_row.root_id,
                                governance_consent_proofs.c.revoked_at.is_(None),
                            )
                        )
                        .order_by(governance_consent_proofs.c.consented_at.desc())
                        .limit(1)
                    )
                ).first()

            epoch = await self._epochs.current(org_id)

        has_active_authority = root_row is not None and consent_row is not None

        return {
            "organization_id": org_id,
            "has_active_authority": has_active_authority,
            "root_authority": {
                "root_id": root_row.root_id,
                "subject_id": root_row.subject_id,
                "issuer": root_row.issuer,
                "root_type": root_row.root_type,
                "verification_method": root_row.verification_method,
                "issued_at": root_row.issued_at,
                "expires_at": root_row.expires_at,
                "canonical_digest": root_row.canonical_digest,
            }
            if root_row
            else None,
            "consent_proof": {
                "consent_id": consent_row.consent_id,
                "scope_description": consent_row.scope_description,
                "purpose": consent_row.purpose,
                "consent_method": consent_row.consent_method,
                "allowed_action_types": json.loads(consent_row.allowed_action_types),
                "allowed_targets": json.loads(consent_row.allowed_targets),
                "consented_at": consent_row.consented_at,
                "canonical_digest": consent_row.canonical_digest,
            }
            if consent_row
            else None,
            "revocation_epoch": epoch.epoch,
        }

    async def revoke_root_authority(
        self,
        actor: Actor,
        *,
        org_id: str,
        root_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """Revoke root authority, cascading to all consent proofs, delegations, and epochs."""
        self._verify_tenant_and_role(actor, org_id, require_owner=True)

        now_iso = _iso()
        async with self._engine.raw.begin() as conn:
            # 1. Lock and advance the revocation epoch
            new_epoch = await bump_epoch_on_connection(conn, org_id)

            # 2. Update canonical root authority
            root_res = await conn.execute(
                update(governance_root_authority_records)
                .where(
                    and_(
                        governance_root_authority_records.c.root_id == root_id,
                        governance_root_authority_records.c.organization_id == org_id,
                        governance_root_authority_records.c.revoked_at.is_(None),
                    )
                )
                .values(
                    revoked_at=now_iso,
                    revoked_by=actor.user_id,
                    revoke_reason=reason,
                )
            )
            if root_res.rowcount == 0:
                raise root_not_found(f"Active root authority {root_id!r} not found for tenant.")

            # 3. Revoke all associated consent proofs
            await conn.execute(
                update(governance_consent_proofs)
                .where(
                    and_(
                        governance_consent_proofs.c.consenting_root_id == root_id,
                        governance_consent_proofs.c.organization_id == org_id,
                        governance_consent_proofs.c.revoked_at.is_(None),
                    )
                )
                .values(
                    revoked_at=now_iso,
                    revoked_by=actor.user_id,
                    revoke_reason=f"Cascading revocation from root {root_id}: {reason}",
                )
            )

            # 4. Revoke Trust Fabric trust root
            await conn.execute(
                update(trust_fabric_trust_roots)
                .where(trust_fabric_trust_roots.c.org_id == org_id)
                .values(status="REVOKED")
            )

            # 5. Revoke all active delegations for the entire organization
            await conn.execute(
                update(governance_delegations)
                .where(
                    and_(
                        governance_delegations.c.org_id == org_id,
                        governance_delegations.c.revoked_at.is_(None),
                    )
                )
                .values(
                    revoked_at=now_iso,
                    revoked_by=actor.user_id,
                    revoke_reason=f"Root authority revoked: {reason}",
                )
            )

            # 6. Audit record
            await self._audit.record(
                action="CUSTOMER_ROOT_AUTHORITY_REVOKED",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                org_id=org_id,
                target_type="root_authority",
                target_id=root_id,
                result="SUCCESS",
                conn=conn,
                metadata={"reason": reason, "epoch": new_epoch},
            )

        # 7. Terminate in-flight executions
        try:
            from responsibleai.isolation.in_flight import InFlightExecutionRegistry
            await InFlightExecutionRegistry.get_instance().terminate_in_flight(organization_id=org_id)
        except Exception:
            pass

        return {
            "status": "REVOKED",
            "root_id": root_id,
            "organization_id": org_id,
            "revoked_at": now_iso,
            "new_epoch": new_epoch,
        }

    # ── Agent Management & Secure Identity Binding ────────────────────────────

    async def register_agent(
        self,
        actor: Actor,
        *,
        org_id: str,
        name: str,
        description: str = "",
        framework: str = "custom",
        purpose: str | None = None,
    ) -> dict[str, Any]:
        """Register an AI agent within the organization.

        INVARIANT: Registration does NOT grant authority. The agent is admitted to the
        identity directory as a distinct principal, but holds zero delegation grants.
        """
        self._verify_tenant_and_role(actor, org_id)

        if not name or not name.strip():
            raise consent_invalid("Agent name cannot be empty.")

        agent_id = f"agent_{uuid.uuid4().hex[:12]}"
        now_iso = _iso()
        meta = {
            "registered_by": actor.user_id,
            "framework": framework,
            "description": description,
            "purpose": purpose,
            "created_at": now_iso,
        }

        async with self._engine.raw.begin() as conn:
            await conn.execute(
                trust_fabric_principals.insert().values(
                    id=agent_id,
                    org_id=org_id,
                    principal_type=PrincipalType.AI_AGENT.value,
                    display_name=name.strip(),
                    lifecycle_state=PrincipalState.ACTIVE.value,
                    metadata_json=json.dumps(meta),
                    created_at=now_iso,
                    updated_at=now_iso,
                )
            )

            await self._audit.record(
                action="AGENT_REGISTERED",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                org_id=org_id,
                target_type="agent",
                target_id=agent_id,
                result="SUCCESS",
                conn=conn,
                metadata=meta,
            )

        return {
            "agent_id": agent_id,
            "organization_id": org_id,
            "display_name": name.strip(),
            "lifecycle_state": PrincipalState.ACTIVE.value,
            "framework": framework,
            "has_delegated_authority": False,
            "created_at": now_iso,
        }

    async def delegate_to_agent(
        self,
        actor: Actor,
        *,
        org_id: str,
        agent_id: str,
        granted_action_types: list[str],
        allowed_targets: list[str],
        purpose: str,
        expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Issue an explicit, attenuated delegation grant from an authorized principal to an agent."""
        self._verify_tenant_and_role(actor, org_id)

        # 1. Verify agent exists in this tenant
        async with self._engine.raw.connect() as conn:
            agent_row = (
                await conn.execute(
                    select(trust_fabric_principals).where(
                        and_(
                            trust_fabric_principals.c.id == agent_id,
                            trust_fabric_principals.c.org_id == org_id,
                        )
                    )
                )
            ).first()
            if not agent_row:
                raise agent_not_found(f"Agent {agent_id!r} not found in organization {org_id!r}.")

            agent_data = dict(agent_row._mapping)
            if agent_data["lifecycle_state"] != PrincipalState.ACTIVE.value:
                raise forbidden(FORBIDDEN, f"Agent {agent_id!r} is disabled or inactive.")

            # Query active root authority
            root_row = (
                await conn.execute(
                    select(governance_root_authority_records).where(
                        and_(
                            governance_root_authority_records.c.organization_id == org_id,
                            governance_root_authority_records.c.revoked_at.is_(None),
                        )
                    ).order_by(governance_root_authority_records.c.issued_at.desc())
                )
            ).first()
            if not root_row:
                raise root_not_found("No active root authority found for organization.")
            root_data = dict(root_row._mapping)

        # 2. Grant delegation with attenuation verification from actor
        delegation = await self._delegations.grant(
            org_id=org_id,
            to_identity_id=agent_id,
            from_identity_id=actor.user_id,
            granted_action_types=frozenset(granted_action_types),
            constraints={"allowed_targets": sorted(allowed_targets)},
            purpose=purpose,
            granted_by=actor.user_id or "system",
            expires_at=expires_at,
        )

        # 3. Create explicit attenuated consent proof for the agent bound to root authority
        agent_consent = build_consent_proof(
            subject_id=actor.user_id or root_data["subject_id"],
            consenting_root_id=root_data["root_id"],
            grantee_id=agent_id,
            scope_description=f"Explicit delegated consent for agent {agent_id}",
            purpose=purpose,
            consent_method=ConsentMethod.SIGNED_DOCUMENT,
            allowed_action_types=tuple(sorted(granted_action_types)),
            allowed_targets=tuple(sorted(allowed_targets)),
            evidence_refs=(f"delegation_grant:{delegation.delegation_id}",),
            expires_at=expires_at or (_now() + timedelta(days=90)),
        )

        async with self._engine.raw.begin() as conn:
            await conn.execute(
                governance_consent_proofs.insert().values(
                    consent_id=agent_consent.consent_id,
                    organization_id=org_id,
                    subject_id=agent_consent.subject_id,
                    consenting_root_id=agent_consent.consenting_root_id,
                    grantee_id=agent_consent.grantee_id,
                    scope_description=agent_consent.scope_description,
                    purpose=agent_consent.purpose,
                    consent_method=agent_consent.consent_method.value,
                    allowed_action_types=json.dumps(list(agent_consent.allowed_action_types)),
                    allowed_targets=json.dumps(list(agent_consent.allowed_targets)),
                    evidence_refs=json.dumps(list(agent_consent.evidence_refs)),
                    consented_at=agent_consent.consented_at.isoformat(),
                    not_before=agent_consent.not_before.isoformat() if agent_consent.not_before else None,
                    expires_at=agent_consent.expires_at.isoformat() if agent_consent.expires_at else None,
                    revoked_at=None,
                    revoked_by=None,
                    revoke_reason=None,
                    canonical_digest=agent_consent.canonical_digest,
                )
            )
            await self._audit.record(
                action="AGENT_DELEGATION_GRANTED",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                org_id=org_id,
                target_type="agent",
                target_id=agent_id,
                result="SUCCESS",
                conn=conn,
                metadata={
                    "delegation_id": delegation.delegation_id,
                    "consent_id": agent_consent.consent_id,
                    "granted_action_types": sorted(granted_action_types),
                    "allowed_targets": sorted(allowed_targets),
                    "purpose": purpose,
                },
            )

        return {
            "delegation_id": delegation.delegation_id,
            "consent_id": agent_consent.consent_id,
            "agent_id": agent_id,
            "organization_id": org_id,
            "granted_action_types": sorted(granted_action_types),
            "allowed_targets": sorted(allowed_targets),
            "purpose": purpose,
            "granted_at": delegation.granted_at.isoformat(),
        }

    async def disable_agent(
        self,
        actor: Actor,
        *,
        org_id: str,
        agent_id: str,
        reason: str = "Disabled by administrator",
    ) -> dict[str, Any]:
        """Disable an agent and revoke all its active delegations transitively."""
        self._verify_tenant_and_role(actor, org_id)

        now_iso = _iso()
        async with self._engine.raw.begin() as conn:
            # Update agent lifecycle state
            res = await conn.execute(
                update(trust_fabric_principals)
                .where(
                    and_(
                        trust_fabric_principals.c.id == agent_id,
                        trust_fabric_principals.c.org_id == org_id,
                    )
                )
                .values(lifecycle_state=PrincipalState.DISABLED.value, updated_at=now_iso)
            )
            if res.rowcount == 0:
                raise agent_not_found(f"Agent {agent_id!r} not found.")

            # Revoke consent proofs for this agent
            await conn.execute(
                update(governance_consent_proofs)
                .where(
                    and_(
                        governance_consent_proofs.c.organization_id == org_id,
                        governance_consent_proofs.c.grantee_id == agent_id,
                        governance_consent_proofs.c.revoked_at.is_(None),
                    )
                )
                .values(
                    revoked_at=now_iso,
                    revoked_by=actor.user_id,
                    revoke_reason=f"Agent {agent_id} disabled: {reason}",
                )
            )

        # Revoke all delegations for this agent branch (cascades and bumps epoch)
        revoked_delegations = await self._delegations.revoke_branch(
            org_id, agent_id, revoked_by=actor.user_id or "admin", reason=reason
        )

        async with self._engine.raw.begin() as conn:
            await self._audit.record(
                action="AGENT_DISABLED",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                org_id=org_id,
                target_type="agent",
                target_id=agent_id,
                result="SUCCESS",
                conn=conn,
                metadata={"reason": reason, "revoked_delegations": revoked_delegations},
            )

        return {
            "status": "DISABLED",
            "agent_id": agent_id,
            "organization_id": org_id,
            "revoked_delegations": revoked_delegations,
        }

    async def list_agents(self, actor: Actor, *, org_id: str) -> list[dict[str, Any]]:
        """List registered agents in the organization and their active delegation status."""
        self._verify_tenant_and_role(actor, org_id)

        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(trust_fabric_principals).where(
                        and_(
                            trust_fabric_principals.c.org_id == org_id,
                            trust_fabric_principals.c.principal_type == PrincipalType.AI_AGENT.value,
                        )
                    )
                )
            ).fetchall()

            result = []
            for row in rows:
                data = dict(row._mapping)
                delegation = await self._delegations.get_active_delegation(org_id, data["id"])
                meta = {}
                if data.get("metadata_json"):
                    try:
                        meta = json.loads(data["metadata_json"])
                    except Exception:
                        pass
                result.append(
                    {
                        "agent_id": data["id"],
                        "organization_id": org_id,
                        "display_name": data["display_name"],
                        "lifecycle_state": data["lifecycle_state"],
                        "has_active_delegation": delegation is not None and delegation.is_active(),
                        "delegation_id": delegation.delegation_id if delegation else None,
                        "framework": meta.get("framework", "custom"),
                        "created_at": data["created_at"],
                    }
                )
            return result
