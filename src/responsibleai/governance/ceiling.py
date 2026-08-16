"""``OrgAuthorityCeiling`` — a structural authority ceiling no per-call
``AuthorityContext`` built for an org can ever exceed, enforced via
``validate_attenuation()`` as the live ``parent_authority`` on every
hosted MCP tool call (see ``mcp/governance_integration.py``).

Distinct from ``governance/policy.py``'s ``Policy`` (first-match-wins
rule evaluation): a ceiling isn't a rule that can match-or-not, it's the
authority envelope every per-call grant is checked against. An org
admin sets "no key under this org may ever authorize a payment above
$X" once, structurally, rather than relying on every individual API
key/agent to have been configured correctly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from responsibleai.governance.models import AuthorityContext


@dataclass
class OrgAuthorityCeiling:
    """All fields default to "unrestricted" — an org with no ceiling
    configured (the default for every org before this feature existed)
    behaves identically to one whose ceiling permits everything.

    ``allowed_action_types``: ``None`` means "don't restrict action
    types via the ceiling at all" -- ``to_authority_context()`` then
    synthesizes a ceiling that grants exactly whatever action type is
    being requested, so the attenuation check's action-type comparison
    is always a no-op pass. Set this to a real list to make the ceiling
    the org's actual tool allowlist, enforced structurally rather than
    per-key.
    """

    org_id: str
    max_value_usd: float | None = None
    allowed_targets: list[str] | None = None
    denied_targets: list[str] | None = None
    max_delegation_depth: int | None = None
    allowed_action_types: list[str] | None = None
    require_approval_for: frozenset[str] = field(default_factory=frozenset)

    def to_authority_context(self, action_type: str) -> AuthorityContext:
        """Builds the ``AuthorityContext`` `validate_attenuation()`
        should treat as the parent for a call proposing *action_type*.
        Called once per dispatched action (not cached), since the
        synthesized ``granted_action_types`` depends on the action being
        evaluated when ``allowed_action_types`` is unset."""
        granted = (
            frozenset(self.allowed_action_types)
            if self.allowed_action_types is not None
            else frozenset({action_type})
        )
        constraints: dict[str, object] = {}
        if self.max_value_usd is not None:
            constraints["max_value_usd"] = self.max_value_usd
        if self.allowed_targets is not None:
            constraints["allowed_targets"] = self.allowed_targets
        if self.denied_targets is not None:
            constraints["denied_targets"] = self.denied_targets
        if self.max_delegation_depth is not None:
            constraints["max_delegation_depth"] = self.max_delegation_depth
        return AuthorityContext(
            delegated_by=f"org_ceiling:{self.org_id}",
            granted_action_types=granted,
            constraints=constraints,
            require_approval_for=self.require_approval_for,
        )
