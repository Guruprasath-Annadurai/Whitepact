"""Community Python SDK — governance client interfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from whitepact_community.authorization import (
    AuthorizationStore,
    ExecutionAuthorization,
    authorize_execution,
    consume_authorization,
    require_signed_cross_host_permit,
)
from whitepact_community.config import CommunityConfig, load_config
from whitepact_community.errors import CommunityCapabilityUnavailable, GovernanceDenied
from whitepact_community.evidence import LocalEvidenceStore
from whitepact_community.gateway import LocalGovernanceKernel
from whitepact_community.models import ActionRequest, AuthorityGrant, DecisionResult
from whitepact_community.policy import Policy, default_local_policy
from whitepact_community.revocation import LocalRevocationRegistry
from whitepact_community.version import API_COMPATIBILITY, __version__


class GovernanceClient:
    """Primary SDK entrypoint for local policy evaluation and governed actions."""

    def __init__(
        self,
        *,
        config: CommunityConfig | None = None,
        kernel: LocalGovernanceKernel | None = None,
    ) -> None:
        self.config = config or CommunityConfig()
        evidence_path = (
            Path(self.config.evidence_path) if self.config.evidence_path else None
        )
        self.kernel = kernel or LocalGovernanceKernel(
            policy=default_local_policy(self.config.org_id),
            evidence=LocalEvidenceStore(evidence_path),
            revocation=LocalRevocationRegistry(),
        )
        self._auth_store = AuthorizationStore()

    @classmethod
    def local(cls, config_path: str | Path | None = None) -> GovernanceClient:
        return cls(config=load_config(config_path))

    @property
    def version(self) -> str:
        return __version__

    @property
    def api_compatibility(self) -> str:
        return API_COMPATIBILITY

    def evaluate(
        self,
        action: ActionRequest,
        authority: AuthorityGrant,
        *,
        policy: Policy | None = None,
        recent_violation_count: int = 0,
    ) -> DecisionResult:
        return self.kernel.evaluate(
            action,
            authority,
            policy=policy,
            recent_violation_count=recent_violation_count,
        )

    def evaluate_or_raise(
        self,
        action: ActionRequest,
        authority: AuthorityGrant,
        **kwargs: Any,
    ) -> DecisionResult:
        result = self.evaluate(action, authority, **kwargs)
        if not result.allowed:
            raise GovernanceDenied(
                f"Action {action.action_type!r} denied with {result.decision.value}",
                decision=result.decision.value,
                reason_codes=result.reason_codes,
            )
        return result

    def authorize(
        self,
        action: ActionRequest,
        authority: AuthorityGrant,
        **kwargs: Any,
    ) -> tuple[DecisionResult, ExecutionAuthorization]:
        decision = self.evaluate_or_raise(action, authority, **kwargs)
        auth = authorize_execution(
            action,
            decision,
            organization_id=authority.organization_id or self.config.org_id,
            ttl_seconds=self.config.authorization_ttl_seconds,
            store=self._auth_store,
        )
        return decision, auth

    def execute_local(
        self,
        action: ActionRequest,
        authority: AuthorityGrant,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Perform one genuine supported local operation under governance."""
        decision, auth = self.authorize(action, authority, **kwargs)
        consume_authorization(auth, action)
        if action.action_type == "local_echo":
            text = action.arguments.get("text", "")
            return {
                "ok": True,
                "echo": text,
                "decision": decision.to_dict(),
                "authorization_id": auth.authorization_id,
            }
        if action.action_type == "local_health":
            return {
                "ok": True,
                "status": "healthy",
                "version": __version__,
                "api_compatibility": API_COMPATIBILITY,
                "decision": decision.to_dict(),
            }
        if action.action_type == "governed_local_action":
            return {
                "ok": True,
                "result": "local_action_completed",
                "payload": action.arguments,
                "decision": decision.to_dict(),
                "authorization_id": auth.authorization_id,
            }
        if action.action_type == "policy_evaluate":
            return {"ok": True, "decision": decision.to_dict()}
        raise CommunityCapabilityUnavailable(
            action.action_type,
            "Not a Community Core local operation.",
        )

    def enterprise_capability(self, name: str) -> None:
        """Explicit rejection surface for SaaS-only operations."""
        raise CommunityCapabilityUnavailable(
            name,
            "Requires private enterprise infrastructure; unavailable in Community Core.",
        )

    def require_signed_cross_host_permit(self) -> None:
        require_signed_cross_host_permit()
