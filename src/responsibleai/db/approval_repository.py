"""Async repository for persisted approval requests (SPEC.md's
`Decision.REQUIRE_APPROVAL` made actionable, Phase 11).

Resolution is a one-way state transition: `PENDING -> APPROVED` or
`PENDING -> DENIED`. `resolve()` raises `ApprovalAlreadyResolvedError`
rather than silently overwriting a prior resolution — a second "who
actually approved this" would be exactly the kind of ambiguity an
approval trail can't tolerate.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import insert, select, update

from responsibleai.db.engine import DatabaseEngine, governance_approvals
from responsibleai.governance.approval import ApprovalRequest, ApprovalStatus

if TYPE_CHECKING:
    from responsibleai.webhooks.manager import WebhookManager


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ApprovalNotFoundError(Exception):
    def __init__(self, approval_id: str) -> None:
        self.approval_id = approval_id
        super().__init__(f"Approval request {approval_id!r} not found.")


class ApprovalAlreadyResolvedError(Exception):
    def __init__(self, approval_id: str, status: str) -> None:
        self.approval_id = approval_id
        self.status = status
        super().__init__(f"Approval {approval_id!r} was already resolved (status={status}).")


def _row_to_request(row: Any) -> ApprovalRequest:
    return ApprovalRequest(
        approval_id=row.id,
        organization_id=row.org_id,
        action_id=row.action_id,
        action_type=row.action_type,
        target=row.target,
        reason_codes=json.loads(row.reason_codes),
        risk_tier=row.risk_tier,
        requested_by=row.requested_by,
        status=ApprovalStatus(row.status),
        requested_at=datetime.fromisoformat(row.requested_at),
        resolved_by=row.resolved_by,
        resolved_at=datetime.fromisoformat(row.resolved_at) if row.resolved_at else None,
        resolution_notes=row.resolution_notes,
    )


class ApprovalRepository:
    """Write, query, and resolve persisted approval requests."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def create(
        self,
        approval: ApprovalRequest,
        *,
        evidence_id: str | None = None,
        webhook_manager: WebhookManager | None = None,
    ) -> ApprovalRequest:
        """Persist *approval* (status must be PENDING) and, if
        *webhook_manager* is supplied, fire `WebhookEvent.APPROVAL_REQUESTED`
        to any org webhook subscribed to it — real notification via the
        existing, tested webhook infrastructure, not a new one.
        `webhook_manager` is optional and keyword-only: this repository
        never requires a webhook subsystem to function.
        """
        async with self._engine.raw.begin() as conn:
            await conn.execute(insert(governance_approvals).values(
                id=approval.approval_id,
                org_id=approval.organization_id,
                action_id=approval.action_id,
                evidence_id=evidence_id,
                action_type=approval.action_type,
                target=approval.target,
                reason_codes=json.dumps(approval.reason_codes),
                risk_tier=approval.risk_tier,
                status=approval.status.value,
                requested_by=approval.requested_by,
                requested_at=approval.requested_at.isoformat(),
            ))

        if webhook_manager is not None:
            from responsibleai.webhooks.models import WebhookEvent

            await webhook_manager.fire(WebhookEvent.APPROVAL_REQUESTED, approval.to_dict())

        return approval

    async def get(self, approval_id: str) -> ApprovalRequest | None:
        async with self._engine.raw.connect() as conn:
            row = (await conn.execute(
                select(governance_approvals).where(governance_approvals.c.id == approval_id)
            )).fetchone()
        return _row_to_request(row) if row else None

    async def list_pending(self, org_id: str | None, *, limit: int = 100) -> list[ApprovalRequest]:
        org_filter = (
            governance_approvals.c.org_id.is_(None)
            if org_id is None
            else governance_approvals.c.org_id == org_id
        )
        query = (
            select(governance_approvals)
            .where(org_filter)
            .where(governance_approvals.c.status == ApprovalStatus.PENDING.value)
            .order_by(governance_approvals.c.requested_at.asc())
            .limit(limit)
        )
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(query)).fetchall()
        return [_row_to_request(r) for r in rows]

    async def resolve(
        self,
        approval_id: str,
        *,
        resolved_by: str,
        outcome: ApprovalStatus,
        notes: str | None = None,
    ) -> ApprovalRequest:
        """Transition a PENDING approval to APPROVED or DENIED.

        Raises `ApprovalNotFoundError` if no such approval exists, and
        `ApprovalAlreadyResolvedError` if it's already been resolved --
        callers must not silently overwrite a prior human decision.
        """
        if outcome is ApprovalStatus.PENDING:
            raise ValueError("outcome must be APPROVED or DENIED, not PENDING")

        current = await self.get(approval_id)
        if current is None:
            raise ApprovalNotFoundError(approval_id)
        if current.is_resolved:
            raise ApprovalAlreadyResolvedError(approval_id, current.status.value)

        resolved_at = _now()
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(governance_approvals)
                .where(governance_approvals.c.id == approval_id)
                .where(governance_approvals.c.status == ApprovalStatus.PENDING.value)
                .values(
                    status=outcome.value,
                    resolved_by=resolved_by,
                    resolved_at=resolved_at,
                    resolution_notes=notes,
                )
            )
        if result.rowcount == 0:
            # Lost a race with a concurrent resolver between the read
            # above and this UPDATE -- the WHERE ... status == PENDING
            # guard is what actually prevents a double-resolution under
            # concurrency; the earlier check is the fast, common-case path.
            refreshed = await self.get(approval_id)
            raise ApprovalAlreadyResolvedError(
                approval_id, refreshed.status.value if refreshed else "UNKNOWN",
            )

        current.status = outcome
        current.resolved_by = resolved_by
        current.resolved_at = datetime.fromisoformat(resolved_at)
        current.resolution_notes = notes
        return current
