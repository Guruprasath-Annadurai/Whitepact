"""Cross-request violation-pattern tracking — what
`GovernanceDecision.QUARANTINE` needed to become reachable, not just a
defined enum member (`governance/models.py`'s module docstring used to
flag this gap explicitly; this module closes it).

Deliberately simple, per the project's own "prefer deterministic
controls" rule and its "no new governance feature unless required"
rule: a fixed-size rolling window and a fixed threshold, not a decay
function or a machine-learned anomaly score. `WhitePactRuntimeGateway`
itself stays synchronous and DB-free (see its own docstring) — the
async DB query that counts recent violations happens here, in the
caller's async context, and the resulting count is passed into
`evaluate()` as a plain int.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from responsibleai.governance.models import GovernanceDecision

if TYPE_CHECKING:
    from responsibleai.db.evidence_repository import EvidenceRepository

# A single, hardcoded default rather than per-org configuration — this
# is a circuit breaker, not a tuning knob orgs are expected to reach
# for on day one. Revisit if real usage shows it needs to be, per the
# same "don't build ahead of a real requirement" principle as the
# rest of this package.
QUARANTINE_VIOLATION_THRESHOLD = 5
QUARANTINE_WINDOW_MINUTES = 60


async def recent_violation_count(
    evidence_repo: EvidenceRepository,
    org_id: str | None,
    agent_id: str,
    *,
    window_minutes: int = QUARANTINE_WINDOW_MINUTES,
) -> int:
    """How many `DENY` decisions *agent_id* has accrued within the last
    *window_minutes*, in *org_id*'s evidence chain. Callers pass the
    result into `WhitePactRuntimeGateway.evaluate(recent_violation_count=...)`;
    a count at or above `QUARANTINE_VIOLATION_THRESHOLD` there produces
    `GovernanceDecision.QUARANTINE` instead of whatever the action would
    otherwise have resolved to."""
    since = (datetime.now(UTC) - timedelta(minutes=window_minutes)).isoformat()
    return await evidence_repo.count_recent(
        org_id, agent_id, GovernanceDecision.DENY.value, since=since,
    )
