# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Intent Contract (Authority Everywhere Phase 4) — the stated goal and
declared bounds an agent commits to *before* it starts taking actions,
so later checks can ask "does this action still match what was
promised," not just "is this action individually allowed."

**Why this is not the same thing as `AuthorityContext`**:
`AuthorityContext.constraint_violation()` (`governance/models.py`)
already checks a value limit, target pattern, or time window — but
those are constraints the *organization* delegated to the agent's
authority grant, set once, usually by an admin, and rarely revisited
per task. `IntentContract` is declared by (or on behalf of) the agent
itself, per task — "for this specific job I'm about to do, here's what
I'm actually trying to accomplish and the bounds I'm committing to
stay inside." An agent can hold broad, org-granted authority and still
choose to declare a narrower intent for one task; `intent_violation()`
below is checked as an additional, independent gate, not a
replacement for `constraint_violation()`.

**Deliberately scoped**: an `IntentContract` is declared once (via
`POST /api/governance/intent-contracts`) and applies to every action
from that `agent_id` until it expires or a newer one is declared — see
`db/intent_repository.py`'s "latest active contract wins" resolution.
This phase does not attempt goal *understanding* (checking that an
action's target/arguments are semantically related to the declared
`goal` string) — `goal` is stored and surfaced for audit/attestation
review, never machine-parsed. That would require interpreting
free-text intent against arbitrary tool arguments, real, separate,
model-assisted work this phase doesn't attempt.
"""

from __future__ import annotations

import fnmatch
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from responsibleai.governance.reason_codes import ReasonCode, format_reason

if TYPE_CHECKING:
    from responsibleai.governance.models import ActionRequest

# Mirrors AuthorityContext's own _VALUE_ARGUMENT_KEYS (models.py) --
# same fixed set of argument names checked for a monetary value, kept
# in sync deliberately rather than imported, since importing from
# models.py here would create a cycle (models.py will import
# IntentContract for the gateway wiring).
_VALUE_ARGUMENT_KEYS = ("amount_usd", "value_usd", "amount")


@dataclass(frozen=True)
class IntentContract:
    """One agent's declared goal and bounds for a task, checked against
    every subsequent `ActionRequest` from that `agent_id` until expiry."""

    organization_id: str
    agent_id: str
    goal: str
    max_value_usd: float | None = None
    allowed_targets: tuple[str, ...] | None = None
    denied_targets: tuple[str, ...] | None = None
    allowed_action_types: tuple[str, ...] | None = None
    contract_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    declared_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    valid_from: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None

    def is_active(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        if current < self.valid_from:
            return False
        if self.expires_at is not None and current >= self.expires_at:
            return False
        return True

    def intent_violation(self, action: ActionRequest) -> str | None:
        """`None` if the action stays within every declared bound (or
        none apply); otherwise a `format_reason()` string. Order:
        denied_targets -> allowed_targets -> allowed_action_types ->
        max_value_usd -- denies checked before allow-lists, narrowest
        scope first, mirroring `AuthorityContext.constraint_violation()`'s
        own ordering convention. Callers are expected to have already
        checked `is_active()` -- this method does not re-check expiry."""
        if self.denied_targets and any(
            fnmatch.fnmatch(action.target, pattern) for pattern in self.denied_targets
        ):
            return format_reason(
                ReasonCode.INTENT_VIOLATED, target=action.target, rule="denied_targets"
            )

        if self.allowed_targets and not any(
            fnmatch.fnmatch(action.target, pattern) for pattern in self.allowed_targets
        ):
            return format_reason(
                ReasonCode.INTENT_VIOLATED, target=action.target, rule="allowed_targets"
            )

        if self.allowed_action_types and action.action_type not in self.allowed_action_types:
            return format_reason(
                ReasonCode.INTENT_VIOLATED,
                action_type=action.action_type,
                rule="allowed_action_types",
            )

        if self.max_value_usd is not None:
            for key in _VALUE_ARGUMENT_KEYS:
                if key in action.arguments:
                    value = action.arguments[key]
                    if isinstance(value, int | float) and value > self.max_value_usd:
                        return format_reason(
                            ReasonCode.INTENT_VIOLATED,
                            argument=key,
                            value=value,
                            limit=self.max_value_usd,
                            rule="max_value_usd",
                        )
                    break

        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "organization_id": self.organization_id,
            "agent_id": self.agent_id,
            "goal": self.goal,
            "max_value_usd": self.max_value_usd,
            "allowed_targets": list(self.allowed_targets) if self.allowed_targets else None,
            "denied_targets": list(self.denied_targets) if self.denied_targets else None,
            "allowed_action_types": (
                list(self.allowed_action_types) if self.allowed_action_types else None
            ),
            "declared_at": self.declared_at.isoformat(),
            "valid_from": self.valid_from.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


def build_intent_contract(
    organization_id: str,
    agent_id: str,
    goal: str,
    *,
    max_value_usd: float | None = None,
    allowed_targets: list[str] | None = None,
    denied_targets: list[str] | None = None,
    allowed_action_types: list[str] | None = None,
    expires_at: datetime | None = None,
) -> IntentContract:
    """Pure assembly, mirroring `outcome.build_outcome_record()`'s own
    shape -- no I/O here; persist via `IntentContractRepository.declare()`."""
    return IntentContract(
        organization_id=organization_id,
        agent_id=agent_id,
        goal=goal,
        max_value_usd=max_value_usd,
        allowed_targets=tuple(allowed_targets) if allowed_targets else None,
        denied_targets=tuple(denied_targets) if denied_targets else None,
        allowed_action_types=tuple(allowed_action_types) if allowed_action_types else None,
        expires_at=expires_at,
    )
