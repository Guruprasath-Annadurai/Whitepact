# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""API-key issuance eligibility. Fail closed. Verification ≠ execution authority."""

from __future__ import annotations

from responsibleai.db.engine import DatabaseEngine
from responsibleai.enterprise.audit import EnterpriseAuditLog
from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.enterprise.issuance import CredentialIssuancePolicy, EligibilityDecision
from responsibleai.enterprise.verification import VerificationService
from responsibleai.rbac.models import Role

__all__ = ["EligibilityDecision", "EligibilityGate"]


class EligibilityGate:
    def __init__(self, engine: DatabaseEngine, verification: VerificationService) -> None:
        self._engine = engine
        self._verification = verification
        self._policy = CredentialIssuancePolicy(engine, verification)
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
        decision = await self._policy.evaluate(
            principal_user_id=principal_user_id,
            organization_id=organization_id,
            environment_id=environment_id,
            requested_scopes=requested_scopes,
            role=role,
        )
        await self.audit.record(
            org_id=organization_id,
            environment_id=environment_id,
            actor_type="human",
            actor_id=principal_user_id or "unknown",
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

    async def assert_eligible_for_api_key(
        self,
        *,
        principal_user_id: str,
        organization_id: str,
        environment_id: str,
        requested_scopes: tuple[str, ...],
        role: Role | None = None,
        request_id: str | None = None,
    ) -> EligibilityDecision:
        decision = await self.may_issue_api_key(
            principal_user_id=principal_user_id,
            organization_id=organization_id,
            environment_id=environment_id,
            requested_scopes=requested_scopes,
            role=role,
            request_id=request_id,
        )
        if not decision.allowed:
            raise EnterpriseError(decision.reason_code, decision.message, 403)
        return decision
