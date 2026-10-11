# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Fail-closed tenant admission for OIDC, SAML, and verifiable credentials.

A verified issuer signature proves who signed the claims. It does not
create a WhitePact tenant, bind a principal to one, or raise that
principal's directory role. Session issuance must call
``admit_sso_principal`` and use only the organization and role it returns.
"""

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.db.org_repository import OrgRepository
from responsibleai.db.web_identity_repository import SsoBinding, WebIdentityRepository
from responsibleai.rbac.models import GovernanceStatus, Plan, Role
from responsibleai.rbac.permissions import known_role, role_privilege_rank


class TenantAdmissionDeniedError(Exception):
    """Authentication stopped before a session or principal record is issued."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class AdmittedPrincipal:
    org_id: str
    org_name: str
    plan: Plan
    role: Role
    user_id: str


def _organization_denial(org: object | None, claimed_org_id: str | None) -> str | None:
    if not claimed_org_id or org is None:
        return "unknown_organization"
    org_id = getattr(org, "id", None)
    if org_id != claimed_org_id:
        return "mismatched_organization"
    if getattr(org, "deactivated_at", None):
        return "deleted_organization"
    status = str(getattr(org, "governance_status", "") or "").upper()
    if status == GovernanceStatus.SUSPENDED.value:
        return "suspended_organization"
    if status != GovernanceStatus.ACTIVE.value:
        return "inactive_organization"
    return None


def _binding_denial(binding: SsoBinding | None) -> str | None:
    if binding is None:
        return "unbound_principal"
    if binding.user_disabled or binding.user_verification_status == "SUSPENDED":
        return "revoked_identity"
    if binding.membership_status == "ABSENT":
        return "mismatched_organization"
    if binding.membership_status != "ACTIVE":
        return "revoked_identity"
    if known_role(binding.role) is None:
        return "invalid_role"
    return None


def _claim_role_denial(claimed_roles: list[str] | None, bound_role: str) -> str | None:
    bound = known_role(bound_role)
    if bound is None:
        return "invalid_role"
    bound_rank = role_privilege_rank(bound)
    for raw in claimed_roles or []:
        if not isinstance(raw, str) or not raw.strip():
            continue
        claimed = known_role(raw)
        if claimed is None:
            return "invalid_role"
        claimed_rank = role_privilege_rank(claimed)
        if claimed_rank > bound_rank or (claimed_rank == bound_rank and claimed != bound):
            return "role_elevation"
    return None


async def admit_sso_principal(
    *,
    org_repo: OrgRepository,
    identity_repo: WebIdentityRepository,
    claimed_org_id: str | None,
    issuer: str | None,
    subject: str | None,
    claimed_roles: list[str] | None,
) -> AdmittedPrincipal:
    """Admit a signed claim only when the tenant and the principal binding agree.

    The returned organization id and role come from WhitePact's directory.
    Claim text is never copied into the session as authority.
    """
    if not issuer or not subject:
        raise TenantAdmissionDeniedError("unbound_principal")
    org = await org_repo.get_org(claimed_org_id) if claimed_org_id else None
    org_reason = _organization_denial(org, claimed_org_id)
    if org_reason is not None or org is None:
        raise TenantAdmissionDeniedError(org_reason or "unknown_organization")
    binding = await identity_repo.lookup_sso_binding(
        issuer=issuer,
        subject=subject,
        org_id=org.id,
    )
    binding_reason = _binding_denial(binding)
    if binding_reason is not None or binding is None:
        raise TenantAdmissionDeniedError(binding_reason or "unbound_principal")
    role_reason = _claim_role_denial(claimed_roles, binding.role)
    if role_reason is not None:
        raise TenantAdmissionDeniedError(role_reason)
    directory_role = known_role(binding.role)
    if directory_role is None:
        raise TenantAdmissionDeniedError("invalid_role")
    plan = org.plan if isinstance(org.plan, Plan) else Plan(str(org.plan))
    return AdmittedPrincipal(
        org_id=org.id,
        org_name=org.name,
        plan=plan,
        role=directory_role,
        user_id=binding.user_id,
    )
