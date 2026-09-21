# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Privileged Surface Guard — Canonical Authorization Chokepoint."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, select

from responsibleai.db.engine import (
    DatabaseEngine,
)
from responsibleai.iam.attribution import PrivilegedAttributionEngine
from responsibleai.iam.enums import (
    ACTION_RISK_TIERS,
    BreakGlassCapability,
    FourEyesStatus,
    JitGrantStatus,
    PrivilegedAction,
    PrivilegeRiskTier,
)
from responsibleai.iam.errors import (
    CrossTenantEscalationError,
    FourEyesRequiredError,
    OperatorBackdoorAttemptError,
    PrivilegedAccessDeniedError,
    SelfApprovalBlockedError,
)
from responsibleai.iam.models import (
    PrivilegedAuthorizationResult,
    PrivilegedCallerContext,
    StepUpProof,
    canonical_hash,
)
from responsibleai.iam.step_up import StepUpVerifier
from responsibleai.rbac.models import Role
from responsibleai.rbac.permissions import has_permission
from responsibleai.trust_fabric.enums import ProofStatus
from responsibleai.trust_fabric.proofs import TrustProofEngine

TRUST_ADMISSION_DENIED_STATES = {
    ProofStatus.NOT_PROVEN,
    ProofStatus.CONFLICTED,
    ProofStatus.EXPIRED,
    ProofStatus.REVOKED,
    ProofStatus.UNKNOWN,
    ProofStatus.REQUIRES_REVIEW,
}

BREAK_GLASS_CAPABILITY_MAP: dict[PrivilegedAction, BreakGlassCapability] = {
    PrivilegedAction.UPDATE_SSO_IDP_CONFIG: BreakGlassCapability.RESTORE_IDP_CONFIGURATION,
    PrivilegedAction.REVOKE_API_KEY: BreakGlassCapability.REVOKE_COMPROMISED_CREDENTIAL,
    PrivilegedAction.RESET_MFA: BreakGlassCapability.REVOKE_COMPROMISED_CREDENTIAL,
    PrivilegedAction.REVOKE_PASSPORT: BreakGlassCapability.REVOKE_COMPROMISED_CREDENTIAL,
    PrivilegedAction.MODIFY_POLICY_RULE: BreakGlassCapability.RESTORE_OPERATIONAL_POLICY_CONFIGURATION,
    PrivilegedAction.MODIFY_WORKFLOW_RULE: BreakGlassCapability.RESTORE_OPERATIONAL_POLICY_CONFIGURATION,
}


class PrivilegedSurfaceGuard:
    """Canonical privileged control-plane authorization chokepoint."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db
        self.step_up = StepUpVerifier(db)
        self.attribution = PrivilegedAttributionEngine(db)
        self.trust_proofs = TrustProofEngine(db)

    async def authorize_privileged_operation(
        self,
        *,
        caller: PrivilegedCallerContext,
        target_org_id: str,
        action: PrivilegedAction,
        target_resource_id: str | None = None,
        step_up_proof: StepUpProof | None = None,
        four_eyes_approval_id: str | None = None,
        jit_grant_id: str | None = None,
        break_glass_session_id: str | None = None,
        context_data: dict[str, Any] | None = None,
    ) -> PrivilegedAuthorizationResult:
        """Authorize a privileged operation enforcing all constitutional security invariants.

        Trust Fabric legitimacy admission is mandatory and unconditional: every call
        must independently resolve the caller's canonical legitimacy claim to PROVEN
        (evaluated fresh, right now, via ``TrustProofEngine.evaluate_privileged_legitimacy``
        -- never from a caller-supplied state) before any role/step-up/four-eyes/JIT/
        break-glass check runs. There is no parameter to omit or flag to leave off: this
        was previously an opt-in ``require_trust_admission`` parameter, which meant a
        caller could bypass admission simply by not passing it -- a security-sensitive
        check must not depend on every caller remembering to opt in, so the parameter
        was removed rather than defaulted differently. A PROVEN result is only a
        prerequisite: it does not itself grant privilege, and every check below still
        applies unchanged. Root recovery and root transfer are deliberately not routed
        through this gate -- those already use their own sovereign proof path in
        recovery.py/transfer.py, and must not be able to reach this method as a bypass.
        """
        from responsibleai.data_governance.backup_defense import assert_restore_readiness_admitted

        assert_restore_readiness_admitted()

        now = datetime.now(UTC).isoformat()

        # Invariant 1: Platform Operator Backdoor Rejection
        # "NO WHITEPACT OPERATOR MAY SILENTLY BECOME A CUSTOMER'S ROOT AUTHORITY."
        if caller.is_platform_operator:
            raise OperatorBackdoorAttemptError(
                "WhitePact platform operators cannot execute customer tenant privileged actions."
            )

        # Invariant 2: Multi-tenant boundary isolation
        if caller.org_id != target_org_id:
            raise CrossTenantEscalationError(
                f"Principal {caller.principal_id!r} of tenant {caller.org_id!r} "
                f"cannot execute privileged actions on tenant {target_org_id!r}."
            )

        # Invariant 2.5: Trust Fabric legitimacy admission (mandatory, unconditional).
        # Consulted only once caller.org_id == target_org_id is established above, so
        # this check is inherently tenant-scoped and cannot be satisfied by a proof
        # evaluated for a different tenant or a different principal_id.
        proof_status = await self.trust_proofs.evaluate_privileged_legitimacy(
            principal_id=caller.principal_id, org_id=target_org_id
        )
        if proof_status in TRUST_ADMISSION_DENIED_STATES:
            raise PrivilegedAccessDeniedError(
                f"Trust legitimacy for principal {caller.principal_id!r} in tenant "
                f"{target_org_id!r} is {proof_status.value}; privileged action "
                f"{action.value} denied."
            )

        # Risk tier determination
        risk_tier = ACTION_RISK_TIERS.get(action, PrivilegeRiskTier.PRIVILEGED_HIGH)

        # Invariant 3: Base role check (or JIT elevation or Break-Glass)
        has_base_role = has_permission(caller.role, Role.ADMIN)
        is_break_glass = False
        is_jit = False

        if break_glass_session_id:
            # Sovereign root actions and tenant destruction are strictly prohibited under break-glass
            if action in {
                PrivilegedAction.TRANSFER_ROOT_AUTHORITY,
                PrivilegedAction.RECOVER_ROOT_AUTHORITY,
                PrivilegedAction.DESTROY_TENANT,
            }:
                raise PrivilegedAccessDeniedError(
                    f"Action {action.value} is strictly prohibited under emergency break-glass."
                )

            from responsibleai.db.engine import iam_break_glass_sessions

            async with self.db.raw.connect() as conn:
                stmt = select(iam_break_glass_sessions).where(
                    and_(
                        iam_break_glass_sessions.c.id == break_glass_session_id,
                        iam_break_glass_sessions.c.org_id == target_org_id,
                    )
                )
                bg_row = (await conn.execute(stmt)).first()
                if not bg_row:
                    raise PrivilegedAccessDeniedError("Invalid emergency break-glass session.")
                bg = dict(bg_row._mapping)
                if bg.get("principal_id") != caller.principal_id:
                    raise PrivilegedAccessDeniedError(
                        "Break-glass session belongs to another principal."
                    )
                if bg["status"] != "ACTIVE" or now >= bg["expires_at"]:
                    raise PrivilegedAccessDeniedError("Break-glass session expired or inactive.")

                # Capability match verification
                if action not in BREAK_GLASS_CAPABILITY_MAP:
                    raise PrivilegedAccessDeniedError(
                        f"Action {action.value} is not permissible under emergency break-glass."
                    )
                required_cap = BREAK_GLASS_CAPABILITY_MAP[action]
                granted_caps = json.loads(bg["capabilities_json"])
                if required_cap.value not in granted_caps:
                    raise PrivilegedAccessDeniedError(
                        f"Break-glass session does not grant required capability {required_cap.value} for {action.value}."
                    )
                is_break_glass = True

        elif jit_grant_id:
            from responsibleai.db.engine import iam_jit_grants

            async with self.db.raw.connect() as conn:
                stmt = select(iam_jit_grants).where(
                    and_(
                        iam_jit_grants.c.id == jit_grant_id,
                        iam_jit_grants.c.org_id == target_org_id,
                        iam_jit_grants.c.principal_id == caller.principal_id,
                    )
                )
                jit_row = (await conn.execute(stmt)).first()
                if not jit_row:
                    raise PrivilegedAccessDeniedError("Invalid JIT access grant.")
                jit = dict(jit_row._mapping)
                if jit["status"] != JitGrantStatus.ACTIVE.value or now >= jit["expires_at"]:
                    raise PrivilegedAccessDeniedError("JIT access grant is expired or inactive.")
                allowed_actions = json.loads(jit["allowed_actions_json"])
                if action.value not in allowed_actions:
                    raise PrivilegedAccessDeniedError(
                        f"Action {action.value} is not authorized by JIT grant."
                    )
                is_jit = True

        elif not has_base_role:
            raise PrivilegedAccessDeniedError(
                f"Principal requires ADMIN or OWNER role. Current role: {caller.role.value}"
            )

        # Invariant 4: Step-Up Reauthentication for HIGH and CRITICAL actions
        step_up_ok = False
        if risk_tier in {PrivilegeRiskTier.PRIVILEGED_HIGH, PrivilegeRiskTier.PRIVILEGED_CRITICAL}:
            step_up_ok = await self.step_up.verify_and_consume_step_up(
                org_id=target_org_id,
                principal_id=caller.principal_id,
                action=action.value,
                risk_tier=risk_tier,
                proof=step_up_proof,
                target_resource_id=target_resource_id,
            )

        # Invariant 5: Four-Eyes Separation of Duties
        four_eyes_ok = False
        if risk_tier == PrivilegeRiskTier.PRIVILEGED_CRITICAL and not is_break_glass:
            if not four_eyes_approval_id:
                raise FourEyesRequiredError(
                    f"Action {action.value} is CRITICAL and requires dual-custody approval."
                )

            from responsibleai.db.engine import iam_four_eyes_requests

            async with self.db.raw.connect() as conn:
                fe_stmt = select(iam_four_eyes_requests).where(
                    and_(
                        iam_four_eyes_requests.c.id == four_eyes_approval_id,
                        iam_four_eyes_requests.c.org_id == target_org_id,
                    )
                )
                fe_row = (await conn.execute(fe_stmt)).first()
                if not fe_row:
                    raise PrivilegedAccessDeniedError("Four-Eyes approval record not found.")

                fe = dict(fe_row._mapping)
                if fe["status"] != FourEyesStatus.APPROVED.value:
                    raise PrivilegedAccessDeniedError(
                        f"Four-Eyes request is in state {fe['status']}, not APPROVED."
                    )

                # Cannot be already consumed
                if fe.get("executed_at") is not None:
                    raise PrivilegedAccessDeniedError(
                        "Four-Eyes approval has already been consumed."
                    )

                # Cannot be expired
                if now >= fe["expires_at"]:
                    raise PrivilegedAccessDeniedError("Four-Eyes approval has expired.")

                # Requester cannot approve their own action!
                if (
                    fe["approver_principal_id"] == caller.principal_id
                    or fe["requester_principal_id"] == fe["approver_principal_id"]
                ):
                    raise SelfApprovalBlockedError(
                        "Requester cannot approve their own privileged request."
                    )

                if fe["action"] != action.value:
                    raise PrivilegedAccessDeniedError("Four-Eyes request action mismatch.")

                # Target resource verification
                if (
                    target_resource_id
                    and fe.get("target_resource_id")
                    and fe["target_resource_id"] != target_resource_id
                ):
                    raise PrivilegedAccessDeniedError("Four-Eyes request target resource mismatch.")

                # Digest and epoch verification if present in parameters
                if fe.get("parameters_json"):
                    try:
                        params = json.loads(fe["parameters_json"])
                        if isinstance(params, dict):
                            if context_data and "policy_digest" in context_data:
                                if (
                                    "policy_digest" in params
                                    and params["policy_digest"] != context_data["policy_digest"]
                                ):
                                    raise PrivilegedAccessDeniedError(
                                        "Four-Eyes approval policy digest mismatch."
                                    )
                            if context_data and "current_epoch" in context_data:
                                if (
                                    "governance_epoch" in params
                                    and params["governance_epoch"] != context_data["current_epoch"]
                                ):
                                    raise PrivilegedAccessDeniedError(
                                        "Four-Eyes approval security epoch mismatch."
                                    )
                    except json.JSONDecodeError:
                        pass

                four_eyes_ok = True

            # Mark Four-Eyes approval as EXECUTED to prevent replay
            from sqlalchemy import update

            async with self.db.raw.begin() as conn:
                await conn.execute(
                    update(iam_four_eyes_requests)
                    .where(iam_four_eyes_requests.c.id == four_eyes_approval_id)
                    .values(status="EXECUTED", executed_at=now)
                )

        # Invariant 6: Sovereign Root Operations must verify Root Identity
        if action in {PrivilegedAction.TRANSFER_ROOT_AUTHORITY, PrivilegedAction.DESTROY_TENANT}:
            if not caller.is_root and caller.role != Role.OWNER:
                raise PrivilegedAccessDeniedError(
                    f"Action {action.value} requires customer Sovereign Root authority."
                )

        # Compute audit digest
        audit_payload = {
            "caller_principal_id": caller.principal_id,
            "org_id": target_org_id,
            "action": action.value,
            "risk_tier": risk_tier.value,
            "target_resource_id": target_resource_id,
            "step_up_verified": step_up_ok,
            "four_eyes_verified": four_eyes_ok,
            "break_glass": is_break_glass,
            "jit": is_jit,
            "timestamp": now,
        }
        audit_hash = canonical_hash(audit_payload)

        result = PrivilegedAuthorizationResult(
            allowed=True,
            risk_tier=risk_tier,
            action=action,
            principal_id=caller.principal_id,
            org_id=target_org_id,
            evaluation_time=now,
            audit_hash=audit_hash,
            step_up_verified=step_up_ok,
            four_eyes_verified=four_eyes_ok,
            break_glass_active=is_break_glass,
        )

        enriched_context = dict(context_data or {})
        enriched_context.update(
            {
                "four_eyes_approval_id": four_eyes_approval_id,
                "jit_grant_id": jit_grant_id,
                "break_glass_session_id": break_glass_session_id,
                "step_up_method": step_up_proof.method.value if step_up_proof else None,
            }
        )

        # Record in tamper-evident audit log linked to Checkpoint-5 evidence
        await self.attribution.record_privileged_event(
            result=result,
            target_resource_id=target_resource_id,
            context_data=enriched_context,
        )

        return result
