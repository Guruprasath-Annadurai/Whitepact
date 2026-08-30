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
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError

from responsibleai.db.engine import DatabaseEngine, governance_approval_votes, governance_approvals
from responsibleai.governance.approval import ApprovalRequest, ApprovalStatus, ApprovalVote
from responsibleai.governance.reason_codes import ReasonCode

if TYPE_CHECKING:
    from responsibleai.governance.models import ActionRequest
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


class SelfApprovalError(Exception):
    """Section 26's invariant: the identity that proposed an action may
    not also be the one who resolves its own REQUIRE_APPROVAL request."""

    reason_code = ReasonCode.SELF_APPROVAL_REJECTED

    def __init__(self, approval_id: str, identity_id: str) -> None:
        self.approval_id = approval_id
        self.identity_id = identity_id
        super().__init__(
            f"Identity {identity_id!r} requested approval {approval_id!r} and cannot resolve it."
        )


class ApprovalExpiredError(Exception):
    """The approval window (`ApprovalRequest.expires_at`) has passed --
    raised uniformly by both `resolve()` and `consume()`, since a human
    decision made against a since-expired context, or an execution
    attempted against one, are both exactly the case an expiry exists
    to prevent."""

    reason_code = ReasonCode.APPROVAL_EXPIRED

    def __init__(self, approval_id: str, expires_at: str | None) -> None:
        self.approval_id = approval_id
        self.expires_at = expires_at
        super().__init__(f"Approval {approval_id!r} expired at {expires_at!r}.")


class ApprovalNotApprovedError(Exception):
    """consume() requires status == APPROVED — covers both "never
    approved" (PENDING/DENIED) and "already executed once"
    (already CONSUMED, i.e. replay) with one check."""

    reason_code = ReasonCode.APPROVAL_REQUIRED

    def __init__(self, approval_id: str, status: str) -> None:
        self.approval_id = approval_id
        self.status = status
        super().__init__(
            f"Approval {approval_id!r} is not APPROVED (status={status}); cannot consume."
        )


class AlreadyVotedError(Exception):
    """The quorum invariant's replay guard: one identity may cast at
    most one vote per approval (enforced by a DB unique constraint on
    (approval_id, resolver_identity_id) as the ultimate backstop under
    concurrency, checked here first for the common case)."""

    def __init__(self, approval_id: str, identity_id: str) -> None:
        self.approval_id = approval_id
        self.identity_id = identity_id
        super().__init__(f"Identity {identity_id!r} already voted on approval {approval_id!r}.")


class ApprovalActionMismatchError(Exception):
    """consume()'s mutation-invariant check: the action being executed
    is not byte-identical to the one a human approved."""

    reason_code = ReasonCode.APPROVAL_ACTION_MISMATCH

    def __init__(self, approval_id: str) -> None:
        self.approval_id = approval_id
        super().__init__(
            f"Approval {approval_id!r} does not match the action presented for execution "
            "(arguments, target, or action_type changed since approval)."
        )


def _row_to_vote(row: Any) -> ApprovalVote:
    return ApprovalVote(
        vote_id=row.id,
        approval_id=row.approval_id,
        resolver_identity_id=row.resolver_identity_id,
        outcome=ApprovalStatus(row.outcome),
        notes=row.notes,
        resolved_at=datetime.fromisoformat(row.resolved_at),
    )


def _row_to_request(row: Any) -> ApprovalRequest:
    return ApprovalRequest(
        approval_id=row.id,
        organization_id=row.org_id,
        action_id=row.action_id,
        action_type=row.action_type,
        target=row.target,
        action_digest=row.action_digest or "",
        reason_codes=json.loads(row.reason_codes),
        risk_tier=row.risk_tier,
        requested_by=row.requested_by,
        status=ApprovalStatus(row.status),
        requested_at=datetime.fromisoformat(row.requested_at),
        expires_at=datetime.fromisoformat(row.expires_at)
        if getattr(row, "expires_at", None)
        else None,
        arguments=json.loads(row.arguments) if getattr(row, "arguments", None) else None,
        required_approvals=getattr(row, "required_approvals", None) or 1,
        resolved_by=row.resolved_by,
        resolved_at=datetime.fromisoformat(row.resolved_at) if row.resolved_at else None,
        resolution_notes=row.resolution_notes,
        purpose=getattr(row, "purpose", None),
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
            await conn.execute(
                insert(governance_approvals).values(
                    id=approval.approval_id,
                    org_id=approval.organization_id,
                    action_id=approval.action_id,
                    evidence_id=evidence_id,
                    action_type=approval.action_type,
                    target=approval.target,
                    action_digest=approval.action_digest,
                    reason_codes=json.dumps(approval.reason_codes),
                    risk_tier=approval.risk_tier,
                    status=approval.status.value,
                    requested_by=approval.requested_by,
                    requested_at=approval.requested_at.isoformat(),
                    expires_at=approval.expires_at.isoformat() if approval.expires_at else None,
                    arguments=json.dumps(approval.arguments)
                    if approval.arguments is not None
                    else None,
                    required_approvals=approval.required_approvals,
                    purpose=approval.purpose,
                )
            )

        if webhook_manager is not None:
            from responsibleai.webhooks.models import WebhookEvent

            await webhook_manager.fire(WebhookEvent.APPROVAL_REQUESTED, approval.to_dict())

        return approval

    async def get(self, approval_id: str) -> ApprovalRequest | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_approvals).where(governance_approvals.c.id == approval_id)
                )
            ).fetchone()
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
        """Cast one vote on a PENDING approval. For the common,
        pre-quorum case (`required_approvals == 1`, every approval's
        default) this behaves exactly as before: one call transitions
        PENDING straight to APPROVED/DENIED. For a quorum > 1 approval,
        a single APPROVED vote records the vote and leaves the approval
        PENDING until enough distinct identities have also voted
        APPROVED; a single DENIED vote is a veto and closes the
        approval immediately regardless of quorum -- unanimous consent
        to proceed, any one objection to stop, the same asymmetry
        `WhitePactRuntimeGateway` itself applies between ALLOW and DENY
        throughout this codebase.

        Raises `ApprovalNotFoundError` if no such approval exists,
        `ApprovalAlreadyResolvedError` if it's already left PENDING
        (APPROVED/DENIED/CONSUMED), `AlreadyVotedError` if *resolved_by*
        already voted on this approval, and `ApprovalExpiredError`/
        `SelfApprovalError` for the same reasons as before.
        """
        if outcome is ApprovalStatus.PENDING:
            raise ValueError("outcome must be APPROVED or DENIED, not PENDING")

        current = await self.get(approval_id)
        if current is None:
            raise ApprovalNotFoundError(approval_id)
        if current.is_resolved:
            raise ApprovalAlreadyResolvedError(approval_id, current.status.value)
        if current.is_expired:
            raise ApprovalExpiredError(
                approval_id, current.expires_at.isoformat() if current.expires_at else None
            )
        # Section 26: the identity that proposed the action cannot also
        # be the one who resolves its own approval requirement — checked
        # even though today's REST layer requires ADMIN role to resolve,
        # since an ADMIN-role API key can still be the same identity
        # that made the original (lower-privilege) request.
        if current.requested_by is not None and resolved_by == current.requested_by:
            raise SelfApprovalError(approval_id, resolved_by)

        existing_vote = await self._get_vote(approval_id, resolved_by)
        if existing_vote is not None:
            raise AlreadyVotedError(approval_id, resolved_by)

        resolved_at = _now()
        vote_id = str(uuid.uuid4())
        try:
            async with self._engine.raw.begin() as conn:
                await conn.execute(
                    insert(governance_approval_votes).values(
                        id=vote_id,
                        approval_id=approval_id,
                        resolver_identity_id=resolved_by,
                        outcome=outcome.value,
                        notes=notes,
                        resolved_at=resolved_at,
                    )
                )
        except IntegrityError as exc:
            # Lost a race with a concurrent vote from the same identity
            # between the read above and this INSERT -- the DB's own
            # UNIQUE(approval_id, resolver_identity_id) constraint is
            # what actually prevents a double vote under concurrency;
            # the earlier check is the fast, common-case path.
            raise AlreadyVotedError(approval_id, resolved_by) from exc

        if outcome is ApprovalStatus.DENIED:
            # A veto: one DENIED vote closes the approval regardless of
            # how many APPROVED votes it may already have (partial
            # consent isn't consent -- SPEC.md's quorum decision).
            return await self._finalize(
                approval_id, current, outcome, resolved_by, resolved_at, notes
            )

        approved_votes = await self._count_votes(approval_id, ApprovalStatus.APPROVED)
        if approved_votes < current.required_approvals:
            # Quorum not yet reached -- record the vote but leave the
            # approval PENDING. Return a shape that reflects "your vote
            # was recorded" without claiming a resolution that hasn't
            # happened: resolved_by/resolved_at/resolution_notes stay
            # unset (None) on the returned object, matching how a
            # genuinely-still-PENDING row reads from the DB.
            return current

        return await self._finalize(approval_id, current, outcome, resolved_by, resolved_at, notes)

    async def _finalize(
        self,
        approval_id: str,
        current: ApprovalRequest,
        outcome: ApprovalStatus,
        resolved_by: str,
        resolved_at: str,
        notes: str | None,
    ) -> ApprovalRequest:
        """Transitions PENDING -> APPROVED/DENIED once quorum is met
        (or immediately, for the single-approver/veto cases). The
        `WHERE ... status == PENDING` guard is the real concurrency
        safeguard -- two votes racing to be the one that reaches quorum
        (or a veto racing a would-be-quorum-closing vote) can only have
        one of them actually perform this transition."""
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
            refreshed = await self.get(approval_id)
            raise ApprovalAlreadyResolvedError(
                approval_id,
                refreshed.status.value if refreshed else "UNKNOWN",
            )

        current.status = outcome
        current.resolved_by = resolved_by
        current.resolved_at = datetime.fromisoformat(resolved_at)
        current.resolution_notes = notes
        return current

    async def _get_vote(self, approval_id: str, resolver_identity_id: str) -> ApprovalVote | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_approval_votes)
                    .where(governance_approval_votes.c.approval_id == approval_id)
                    .where(governance_approval_votes.c.resolver_identity_id == resolver_identity_id)
                )
            ).fetchone()
        return _row_to_vote(row) if row else None

    async def _count_votes(self, approval_id: str, outcome: ApprovalStatus) -> int:
        async with self._engine.raw.connect() as conn:
            result = (
                await conn.execute(
                    select(func.count())
                    .select_from(governance_approval_votes)
                    .where(governance_approval_votes.c.approval_id == approval_id)
                    .where(governance_approval_votes.c.outcome == outcome.value)
                )
            ).scalar()
        return int(result or 0)

    async def list_votes(self, approval_id: str) -> list[ApprovalVote]:
        """Every vote cast on *approval_id* so far, oldest first -- the
        quorum audit trail `ApprovalRequest.to_dict()` itself doesn't
        carry (it only reflects the single vote that closed, or is
        closing, the approval)."""
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(governance_approval_votes)
                    .where(governance_approval_votes.c.approval_id == approval_id)
                    .order_by(governance_approval_votes.c.resolved_at.asc())
                )
            ).fetchall()
        return [_row_to_vote(r) for r in rows]

    async def consume(self, approval_id: str, *, action: ActionRequest) -> ApprovalRequest:
        """The execution-binding check (Sections 24/25/27/51): an
        executor must call this — and only proceed if it returns
        normally — immediately before actually running an action that
        was gated behind `REQUIRE_APPROVAL`.

        Enforces, in one atomic operation:
        - **Mutation invariant**: raises `ApprovalActionMismatchError`
          unless *action*'s digest is byte-identical to what was
          approved (`ApprovalRequest.matches_action`) — a changed
          amount, target, or argument after approval is never silently
          honored.
        - **Replay protection**: the `WHERE status = 'APPROVED'` guard
          (same race-safe pattern as `resolve()`) means a second call
          for the same approval — whether the exact same action or a
          mutated one — always fails, because the first successful
          call already transitioned it to CONSUMED. There is no way to
          execute against one human approval twice.
        - **Not-yet-approved / already-denied**: raises
          `ApprovalNotApprovedError` uniformly for PENDING, DENIED, or
          already-CONSUMED — the caller doesn't need to branch on why,
          only that execution must not proceed.

        Deliberately does not accept an `expected_digest` parameter
        from the caller — recomputing it from a freshly-constructed
        `ActionRequest` (the one about to actually execute) is the
        entire point; trusting a caller-supplied digest would let a
        compromised caller simply pass back whatever digest is stored.
        """
        current = await self.get(approval_id)
        if current is None:
            raise ApprovalNotFoundError(approval_id)
        if current.status is not ApprovalStatus.APPROVED:
            raise ApprovalNotApprovedError(approval_id, current.status.value)
        if current.is_expired:
            raise ApprovalExpiredError(
                approval_id, current.expires_at.isoformat() if current.expires_at else None
            )
        if not current.matches_action(action):
            raise ApprovalActionMismatchError(approval_id)

        consumed_at = _now()
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(governance_approvals)
                .where(governance_approvals.c.id == approval_id)
                .where(governance_approvals.c.status == ApprovalStatus.APPROVED.value)
                .values(status=ApprovalStatus.CONSUMED.value)
            )
        if result.rowcount == 0:
            # Lost a race with a concurrent consume() call between the
            # read above and this UPDATE -- exactly the replay scenario
            # this method exists to prevent (two executors racing to
            # spend the same approval). Whichever one loses the race
            # gets this, not a silently-successful double execution.
            refreshed = await self.get(approval_id)
            raise ApprovalNotApprovedError(
                approval_id,
                refreshed.status.value if refreshed else "UNKNOWN",
            )

        current.status = ApprovalStatus.CONSUMED
        current.resolved_at = current.resolved_at or datetime.fromisoformat(consumed_at)
        return current
