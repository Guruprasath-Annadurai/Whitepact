# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Canonical credential issuance policy.

Repository insertion is not a policy decision. Every hosted issuance path
must call this policy before a reusable credential exists.

Questions answered, in order:
1. Who is the human?
2. Is identity IDENTITY_VERIFIED?
3. Which workspace/org?
4. Is workspace/org active?
5. Is membership active?
6. Is organization verification sufficient?
7. Is RBAC sufficient?
8. Which environment?
9. Which scopes?
10. Is a security/abuse hold present?
11. Who becomes accountable_human_user_id?
12. May the credential be issued?

IDENTITY_VERIFIED is required for development, staging, and production.
BASIC_VERIFIED is never sufficient for reusable API credentials.
IDENTITY_VERIFIED is not execution authority.
"""

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
from responsibleai.enterprise.errors import (
    API_KEY_ISSUANCE_NOT_ALLOWED,
    FORBIDDEN,
    IDENTITY_VERIFICATION_REQUIRED,
    ORGANIZATION_VERIFICATION_REQUIRED,
    VERIFICATION_REVIEW_REQUIRED,
    VERIFICATION_SUSPENDED,
)
from responsibleai.enterprise.roles import CANONICAL_SCOPES, Permission, has_rbac_permission
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
    accountable_human_user_id: str | None = None


class CredentialIssuancePolicy:
    """Single authoritative gate for reusable human and service-account credentials."""

    def __init__(self, engine: DatabaseEngine, verification: VerificationService) -> None:
        self._engine = engine
        self._verification = verification

    async def evaluate(
        self,
        *,
        principal_user_id: str,
        organization_id: str,
        environment_id: str,
        requested_scopes: tuple[str, ...],
        role: Role | None = None,
    ) -> EligibilityDecision:
        async with self._engine.raw.connect() as conn:
            user = (
                await conn.execute(select(web_users).where(web_users.c.id == principal_user_id))
            ).fetchone()
            org = (
                await conn.execute(
                    select(organizations).where(organizations.c.id == organization_id)
                )
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
                    select(enterprise_environments).where(
                        enterprise_environments.c.id == environment_id
                    )
                )
            ).fetchone()

        def denied(code: str, message: str, env_type: str | None = None) -> EligibilityDecision:
            return EligibilityDecision(
                False,
                code,
                message,
                env_type,
                getattr(org, "workspace_kind", None) if org else None,
                principal_user_id or None,
            )

        if not principal_user_id:
            return denied(
                API_KEY_ISSUANCE_NOT_ALLOWED, "Authenticated human principal is required."
            )
        if user is None or user.disabled:
            return denied(API_KEY_ISSUANCE_NOT_ALLOWED, "Principal is missing or disabled.")
        if getattr(user, "abuse_hold", 0):
            return denied(API_KEY_ISSUANCE_NOT_ALLOWED, "Account is on an abuse hold.")
        if org is None:
            return denied(API_KEY_ISSUANCE_NOT_ALLOWED, "Organization not found.")
        if org.governance_status != GovernanceStatus.ACTIVE.value or org.deactivated_at:
            return denied(API_KEY_ISSUANCE_NOT_ALLOWED, "Organization is not active.")
        if membership is None or membership.status != "ACTIVE":
            return denied(API_KEY_ISSUANCE_NOT_ALLOWED, "Active membership is required.")
        member_role = role or role_from_str(membership.role)
        if not has_rbac_permission(member_role, Permission.API_KEYS_CREATE):
            return denied(FORBIDDEN, "Role cannot issue API keys.")
        if env is None:
            return denied(API_KEY_ISSUANCE_NOT_ALLOWED, "Environment not found.")
        if env.org_id != organization_id:
            return denied(
                API_KEY_ISSUANCE_NOT_ALLOWED, "Environment does not belong to this organization."
            )
        if env.status != "ACTIVE":
            return denied(API_KEY_ISSUANCE_NOT_ALLOWED, "Environment is not active.")

        unknown = set(requested_scopes) - CANONICAL_SCOPES
        if unknown:
            return denied(API_KEY_ISSUANCE_NOT_ALLOWED, "Unknown API scopes requested.", env.type)

        human = await self._verification.get_human_status(principal_user_id)
        human_status = human["status"]
        if human_status == "SUSPENDED":
            return denied(VERIFICATION_SUSPENDED, "Identity verification is suspended.", env.type)
        if human_status == "REVIEW_REQUIRED":
            return denied(
                VERIFICATION_REVIEW_REQUIRED, "Identity verification is under review.", env.type
            )
        if human_status != "IDENTITY_VERIFIED":
            return denied(
                IDENTITY_VERIFICATION_REQUIRED,
                "IDENTITY_VERIFIED is required to issue reusable API credentials "
                "in every environment. BASIC_VERIFIED and email verification are not sufficient.",
                env.type,
            )

        workspace_kind = getattr(org, "workspace_kind", None) or "ORGANIZATION"
        if workspace_kind == "ORGANIZATION" and env.type == "PRODUCTION":
            org_v = await self._verification.get_org_status(organization_id)
            if org_v["status"] == "SUSPENDED":
                return denied(
                    VERIFICATION_SUSPENDED, "Organization verification is suspended.", env.type
                )
            if org_v["status"] != "ORGANIZATION_VERIFIED":
                return denied(
                    ORGANIZATION_VERIFICATION_REQUIRED,
                    "Verified organization identity is required for production API keys.",
                    env.type,
                )
        if env.type == "PRODUCTION" and not human.get("email_verified"):
            return denied(IDENTITY_VERIFICATION_REQUIRED, "Verified email is required.", env.type)
        if PRODUCTION_GATE_B_OPEN:
            return denied(API_KEY_ISSUANCE_NOT_ALLOWED, "Unexpected production gate state.")

        return EligibilityDecision(
            True,
            "API_ELIGIBILITY_GRANTED",
            "Issuance permitted by policy.",
            env.type,
            workspace_kind,
            principal_user_id,
        )

    async def assert_sponsor_eligible(
        self,
        *,
        principal_user_id: str,
        organization_id: str,
        role: Role | None = None,
    ) -> EligibilityDecision:
        """Service-account sponsorship uses the same verified-human invariant."""
        async with self._engine.raw.connect() as conn:
            env = (
                await conn.execute(
                    select(enterprise_environments).where(
                        enterprise_environments.c.org_id == organization_id,
                        enterprise_environments.c.type == "DEVELOPMENT",
                    )
                )
            ).fetchone()
        if env is None:
            return EligibilityDecision(
                False,
                API_KEY_ISSUANCE_NOT_ALLOWED,
                "Development environment is required to bind service-account sponsorship.",
                None,
                None,
                principal_user_id,
            )
        return await self.evaluate(
            principal_user_id=principal_user_id,
            organization_id=organization_id,
            environment_id=env.id,
            requested_scopes=("usage:read",),
            role=role,
        )
