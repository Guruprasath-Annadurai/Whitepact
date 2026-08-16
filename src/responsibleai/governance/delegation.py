"""Delegation Graph domain model (Core Invariant #2): the persisted
record of who delegated authority to whom, distinct from
``AuthorityContext.delegation_chain`` (an in-memory, per-call ordered
list of identity_ids an already-constructed authority carries). This
module is the actual graph -- reconstructable, queryable, revocable --
``db/delegation_repository.py`` is where it's persisted and where
``revoke_branch()`` (cascading revocation) and ``explain_authority()``
live.

Deliberately one active delegation per identity at a time (a second
``grant()`` call for the same ``to_identity_id`` supersedes the prior
one -- see the repository's own docstring for why), not a
multi-authority-per-identity model -- matches the concrete requirement
("what does this identity currently hold") rather than a more general
but unneeded multi-grant algebra.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from responsibleai.governance.models import AuthorityContext


@dataclass(frozen=True)
class DelegationRecord:
    delegation_id: str
    org_id: str
    # None means a root grant -- from a human/org owner, not from
    # another delegated identity. A non-None value must itself be an
    # identity with its own (possibly also-root) delegation record.
    from_identity_id: str | None
    to_identity_id: str
    granted_action_types: frozenset[str]
    constraints: dict[str, Any]
    require_approval_for: frozenset[str]
    purpose: str
    granted_by: str
    granted_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    revoked_by: str | None = None
    revoke_reason: str | None = None

    def is_active(self, *, now: datetime | None = None) -> bool:
        """Continuous re-authorization's actual check: a delegation
        that was valid at grant time is not valid forever -- revocation
        and expiry are both checked fresh, not just at grant time."""
        current = now or datetime.now(UTC)
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and current >= self.expires_at:
            return False
        return True

    def to_authority_context(self) -> AuthorityContext:
        return AuthorityContext(
            delegated_by=self.from_identity_id or self.granted_by,
            granted_action_types=self.granted_action_types,
            constraints=self.constraints,
            require_approval_for=self.require_approval_for,
        )
