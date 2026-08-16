"""Autonomy Budget (v3 authority-layer work): a rolling-window cap on
how many actions an identity may execute WITHOUT a human in the loop
before the gateway forces the next one to ``REQUIRE_APPROVAL`` --
distinct from every other volume-based control already built:

- ``quarantine.py`` reacts to a pattern of *bad* (``DENY``) outcomes.
- ``workflow.py`` reacts to a *dangerous combination* of individually-
  permitted actions.
- ``cost/models.py``'s ``BudgetPolicy`` caps dollar spend, not action
  count, and isn't consulted by the governance gateway at all.

This is different in kind: an agent can do everything "right" -- every
individual action correctly ``ALLOW``ed -- and still trip this, purely
because it's been running unsupervised for too long. The point is
forcing a periodic human check-in on high-autonomy agents, not
punishing bad behavior.

Same "``WhitePactRuntimeGateway`` stays synchronous and DB-free"
precedent as ``quarantine.py``: the async count query happens here, in
the caller's async context, and the resulting int is passed into
``evaluate()`` as a plain argument.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from responsibleai.governance.models import GovernanceDecision

if TYPE_CHECKING:
    from responsibleai.db.evidence_repository import EvidenceRepository


@dataclass(frozen=True)
class AutonomyBudgetPolicy:
    """No default cap and no module-level constant (unlike
    ``QUARANTINE_VIOLATION_THRESHOLD``) -- unlike quarantine, which is a
    circuit breaker every org gets for free, an autonomy budget is a
    genuine per-org policy choice (how much unsupervised autonomy is
    acceptable varies enormously by org and by agent), so it's always
    explicitly configured, never silently defaulted on."""

    max_autonomous_actions: int
    window_minutes: int = 60


async def recent_autonomous_action_count(
    evidence_repo: EvidenceRepository,
    org_id: str | None,
    agent_id: str,
    *,
    window_minutes: int,
) -> int:
    """How many ``ALLOW``/``ALLOW_WITH_REDACTION`` decisions *agent_id*
    has accrued within the last *window_minutes* -- both are outcomes
    that actually executed with no human decision in the loop, unlike
    ``REQUIRE_APPROVAL`` (a human looked) or ``DENY``/``QUARANTINE``
    (never ran at all). Two ``count_recent()`` calls summed, not a new
    query method -- ``EvidenceRepository.count_recent()`` already takes
    an arbitrary decision value; no DB-layer change needed for this
    feature."""
    since = (datetime.now(UTC) - timedelta(minutes=window_minutes)).isoformat()
    allow_count = await evidence_repo.count_recent(
        org_id, agent_id, GovernanceDecision.ALLOW.value, since=since
    )
    redacted_count = await evidence_repo.count_recent(
        org_id, agent_id, GovernanceDecision.ALLOW_WITH_REDACTION.value, since=since
    )
    return allow_count + redacted_count
