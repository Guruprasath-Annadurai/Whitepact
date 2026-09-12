# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Privileged Surface Guard — Canonical Authorization Chokepoint."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, select

from responsibleai.db.engine import (
    DatabaseEngine,
)
from responsibleai.iam.attribution import PrivilegedAttributionEngine
from responsibleai.iam.enums import (
    ACTION_RISK_TIERS,
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


class PrivilegedSurfaceGuard:
    """Canonical privileged control-plane authorization chokepoint."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db
        self.step_up = StepUpVerifier(db)
        self.attribution = PrivilegedAttributionEngine(db)

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
        """Authorize a privileged operation enforcing all constitutional security invariants."""
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

        # Risk tier determination
        risk_tier = ACTION_RISK_TIERS.get(action, PrivilegeRiskTier.PRIVILEGED_HIGH)

        # Invariant 3: Base role check (or JIT elevation or Break-Glass)
        has_base_role = has_permission(caller.role, Role.ADMIN)
        is_break_glass = False
        is_jit = False

        if break_glass_session_id:
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
                if bg["status"] != "ACTIVE" or now >= bg["expires_at"]:
                    raise PrivilegedAccessDeniedError("Break-glass session expired or inactive.")
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

                # Requester cannot approve their own action!
                if fe["approver_principal_id"] == caller.principal_id:
                    raise SelfApprovalBlockedError("Requester cannot approve their own privileged request.")

                if fe["action"] != action.value:
                    raise PrivilegedAccessDeniedError("Four-Eyes request action mismatch.")

                four_eyes_ok = True

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

        # Record in tamper-evident audit log
        await self.attribution.record_privileged_event(
            result=result,
            target_resource_id=target_resource_id,
            context_data=context_data,
        )

        return result
