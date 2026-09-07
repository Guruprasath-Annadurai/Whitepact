# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Canonical normalization of authenticated requests, without granting authority."""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field

from responsibleai.governance.models import ActionRequest
from responsibleai.rbac.models import OrgContext

_AUTH_METHODS = frozenset({"api_key", "oidc", "saml", "oauth", "session", "vc"})


@dataclass(frozen=True)
class GovernanceContext:
    organization_id: str
    subject_id: str
    authentication_method: str
    membership_reference: str
    action: ActionRequest
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str | None = None
    trace_id: str | None = None

    @classmethod
    def from_authenticated(
        cls,
        auth: OrgContext,
        action: ActionRequest,
        *,
        authentication_method: str,
        request_id: str | None = None,
        deployment_id: str | None = None,
    ) -> GovernanceContext:
        """Called only after the existing credential/session membership checks.

        OrgContext is an internal verified credential context, never a request
        body model. Its role, plan and OAuth scopes do not become runtime grants.
        The action is copied so later mutations to a parsed payload cannot change
        the normalized request. The permit separately binds its complete digest.
        """
        if auth.is_legacy or not auth.org_id or not auth.key_id:
            raise ValueError("Tenant-scoped authenticated membership required")
        if authentication_method not in _AUTH_METHODS:
            raise ValueError("Unsupported authentication method")
        identity = action.agent.identity
        if (
            identity.identity_id != auth.key_id
            or identity.org_id != auth.org_id
            or action.agent.organization_id != auth.org_id
        ):
            raise ValueError("Authenticated identity or organization mismatch")
        return cls(
            organization_id=auth.org_id,
            subject_id=auth.key_id,
            authentication_method=authentication_method,
            membership_reference=auth.key_id,
            action=copy.deepcopy(action),
            request_id=request_id or str(uuid.uuid4()),
            deployment_id=deployment_id,
        )

    def validate_binding(self) -> None:
        identity = self.action.agent.identity
        if (
            not self.organization_id
            or not self.subject_id
            or self.authentication_method not in _AUTH_METHODS
            or self.membership_reference != self.subject_id
            or identity.identity_id != self.subject_id
            or identity.org_id != self.organization_id
            or self.action.agent.organization_id != self.organization_id
        ):
            raise ValueError("Governance context binding mismatch")
