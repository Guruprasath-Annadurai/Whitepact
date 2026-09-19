# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""API-key issuance eligibility. Fail closed. Verification ≠ execution authority."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from responsibleai.db.engine import (
    DatabaseEngine,
    enterprise_environments,
    organizations,
    web_memberships,
    web_users,
)
from responsibleai.enterprise.audit import EnterpriseAuditLog
from responsibleai.enterprise.errors import (
    API_KEY_ISSUANCE_NOT_ALLOWED,
    FORBIDDEN,
    IDENTITY_VERIFICATION_REQUIRED,
    ORGANIZATION_VERIFICATION_REQUIRED,
    VERIFICATION_REVIEW_REQUIRED,
    VERIFICATION_SUSPENDED,
)
from responsibleai.enterprise.roles import Permission, has_rbac_permission
from responsibleai.enterprise.verification import VerificationService
from responsibleai.rbac.models import GovernanceStatus, Role
from responsibleai.rbac.permissions import role_from_str
from responsibleai.runtime.gate import PRODUCTION_GATE_B_OPEN


@dataclass(frozen=True)
class EligibilityDecision:
    allowed: bool
    reason_code: str
    message: str
    environment_type: str | None = None
    workspace_kind: str | None = None


class EligibilityGate:
    def __init__(self, engine: DatabaseEngine, verification: VerificationService) -> None:
        self._engine = engine
        self._verification = verification
        self.audit = EnterpriseAuditLog(engine)

    async def may_issue_api_key(
        self,
        *,
        principal_user_id: str,
        organization_id: str,
        environment_id: str,
        requested_scopes: tuple[str, ...],
        role: Role | None = None,
        request_id: str | None = None,
    ) -> EligibilityDecision:
        async with self._engine.raw.connect() as conn:
            user = (
                await conn.execute(select(web_users).where(web_users.c.id == principal_user_id))
            ).fetchone()
            org = (
                await conn.execute(select(organizations).where(organizations.c.id == organization_id))
            ).fetchone()
            membership = (
                await conn.execute(
                    select(web_memberships).where(
                        web_memberships.c.user_id == principal_user_id,
                        web_memberships.c.org_id == organization_id,
                    )
                )
            ).fetchone()
            env = (
                await conn.execute(
                    select(enterprise_environments).where(enterprise_environments.c.id == environment_id)
                )
            ).fetchone()

        async def finish(decision: EligibilityDecision) -> EligibilityDecision:
            await self.audit.record(
                org_id=organization_id,
                environment_id=environment_id,
                actor_type="human",
                actor_id=principal_user_id,
                action="api_eligibility.granted" if decision.allowed else "api_eligibility.denied",
                target_type="environment",
                target_id=environment_id,
                result="ALLOWED" if decision.allowed else "DENIED",
                request_id=request_id,
                metadata={
                    "reason_code": decision.reason_code,
                    "scopes": list(requested_scopes),
                    "environment_type": decision.environment_type,
                },
            )
            return decision

        def denied(code: str, message: str, env_type: str | None = None) -> EligibilityDecision:
            return EligibilityDecision(
                False,
                code,
                message,
                env_type,
                getattr(org, "workspace_kind", None) if org else None,
            )

        if user is None or user.disabled:
            return await finish(denied(API_KEY_ISSUANCE_NOT_ALLOWED, "Principal is missing or disabled."))
        if getattr(user, "abuse_hold", 0):
            return await finish(denied(API_KEY_ISSUANCE_NOT_ALLOWED, "Account is on an abuse hold."))
        if org is None:
            return await finish(denied(API_KEY_ISSUANCE_NOT_ALLOWED, "Organization not found."))
        if org.governance_status != GovernanceStatus.ACTIVE.value or org.deactivated_at:
            return await finish(denied(API_KEY_ISSUANCE_NOT_ALLOWED, "Organization is not active."))
        if membership is None or membership.status != "ACTIVE":
            return await finish(denied(API_KEY_ISSUANCE_NOT_ALLOWED, "Active membership is required."))
        member_role = role or role_from_str(membership.role)
        if not has_rbac_permission(member_role, Permission.API_KEYS_CREATE):
            return await finish(denied(FORBIDDEN, "Role cannot issue API keys."))
        if env is None:
            return await finish(denied(API_KEY_ISSUANCE_NOT_ALLOWED, "Environment not found."))
        if env.org_id != organization_id:
            return await finish(
                denied(API_KEY_ISSUANCE_NOT_ALLOWED, "Environment does not belong to this organization.")
            )
        if env.status != "ACTIVE":
            return await finish(denied(API_KEY_ISSUANCE_NOT_ALLOWED, "Environment is not active."))

        human = await self._verification.get_human_status(principal_user_id)
        human_status = human["status"]
        if human_status == "SUSPENDED":
            return await finish(
                denied(VERIFICATION_SUSPENDED, "Identity verification is suspended.", env.type)
            )
        if human_status == "REVIEW_REQUIRED":
            return await finish(
                denied(VERIFICATION_REVIEW_REQUIRED, "Identity verification is under review.", env.type)
            )
        if human_status in {"REJECTED", "UNVERIFIED"}:
            return await finish(
                denied(
                    IDENTITY_VERIFICATION_REQUIRED,
                    "Verified identity is required to issue API keys.",
                    env.type,
                )
            )
        if env.type in {"STAGING", "PRODUCTION"} and human_status != "IDENTITY_VERIFIED":
            return await finish(
                denied(
                    IDENTITY_VERIFICATION_REQUIRED,
                    "Strong individual identity verification is required for this environment.",
                    env.type,
                )
            )
        if env.type == "DEVELOPMENT" and human_status not in {"BASIC_VERIFIED", "IDENTITY_VERIFIED"}:
            return await finish(
                denied(IDENTITY_VERIFICATION_REQUIRED, "Basic verification is required.", env.type)
            )

        workspace_kind = getattr(org, "workspace_kind", None) or "ORGANIZATION"
        if workspace_kind == "ORGANIZATION" and env.type == "PRODUCTION":
            org_v = await self._verification.get_org_status(organization_id)
            if org_v["status"] == "SUSPENDED":
                return await finish(
                    denied(VERIFICATION_SUSPENDED, "Organization verification is suspended.", env.type)
                )
            if org_v["status"] != "ORGANIZATION_VERIFIED":
                return await finish(
                    denied(
                        ORGANIZATION_VERIFICATION_REQUIRED,
                        "Verified organization identity is required for production API keys.",
                        env.type,
                    )
                )
        if workspace_kind == "INDIVIDUAL" and env.type == "PRODUCTION" and human_status != "IDENTITY_VERIFIED":
            return await finish(
                denied(
                    IDENTITY_VERIFICATION_REQUIRED,
                    "Verified individual identity is required for production API keys.",
                    env.type,
                )
            )
        if env.type == "PRODUCTION" and not human.get("email_verified"):
            return await finish(
                denied(IDENTITY_VERIFICATION_REQUIRED, "Verified email is required.", env.type)
            )
        if env.type == "PRODUCTION" and human_status == "BASIC_VERIFIED":
            return await finish(
                denied(
                    IDENTITY_VERIFICATION_REQUIRED,
                    "Email verification alone is not sufficient for production API credentials.",
                    env.type,
                )
            )
        if PRODUCTION_GATE_B_OPEN:
            return await finish(
                denied(API_KEY_ISSUANCE_NOT_ALLOWED, "Unexpected production gate state.")
            )

        return await finish(
            EligibilityDecision(
                True,
                "API_ELIGIBILITY_GRANTED",
                "Issuance permitted by policy.",
                env.type,
                workspace_kind,
            )
        )
