# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Employee offboarding steps for WhitePact Cloud (logical; provider hooks are external)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OffboardingState:
    employee_id: str
    identity_disabled: bool = False
    sessions_revoked: bool = False
    grants_revoked: bool = False
    provider_permissions_removed: bool = False
    api_credentials_revoked: bool = False
    admin_access_terminated: bool = False
    audit_record_id: str | None = None
    steps_completed: list[str] = field(default_factory=list)


def run_offboarding(
    employee_id: str,
    *,
    revoke_session_fn,
    revoke_grants_fn,
    revoke_provider_fn,
    audit_fn,
) -> OffboardingState:
    state = OffboardingState(employee_id=employee_id)
    audit_fn(employee_id, "offboarding_started")
    state.identity_disabled = True
    state.steps_completed.append("identity_disabled")

    revoke_session_fn(employee_id)
    state.sessions_revoked = True
    state.steps_completed.append("sessions_revoked")

    revoke_grants_fn(employee_id)
    state.grants_revoked = True
    state.steps_completed.append("grants_revoked")

    revoke_provider_fn(employee_id)
    state.provider_permissions_removed = True
    state.api_credentials_revoked = True
    state.admin_access_terminated = True
    state.steps_completed.append("provider_access_revoked")

    state.audit_record_id = audit_fn(employee_id, "offboarding_complete")
    return state


def offboarding_complete(state: OffboardingState) -> bool:
    return all(
        [
            state.identity_disabled,
            state.sessions_revoked,
            state.grants_revoked,
            state.provider_permissions_removed,
            state.api_credentials_revoked,
            state.admin_access_terminated,
        ]
    )
