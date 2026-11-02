"""Concurrency / race-condition tests.

Several repositories in this codebase carry an explicit, documented
claim of race-safety in their own docstrings (`ApprovalRepository.consume()`'s
conditional UPDATE, `ApprovalRepository.resolve()`'s unique-constraint
backstop, `EvidenceRepository`'s `asyncio.Lock()` around the hash chain).
This file turns those documented claims into verified ones by actually
firing concurrent `asyncio.gather()` calls at them -- not just trusting
the docstring.

It also honestly tests a write path that carries **no** such claim
(`recent_autonomous_action_count()`'s check-then-act window, the same
plain-`SELECT COUNT(*)`-then-decide shape `quarantine.py`'s
`recent_violation_count()` also has) -- see
`TestAutonomyBudgetConcurrency` for what that test actually found, not
what it was expected to find. A race test that only ever confirms
existing protections work is missing half the point.

All fixtures use `create_engine(":memory:")`, which is backed by
SQLAlchemy `StaticPool` (a single shared `aiosqlite` connection across
every checkout -- see `db/engine.py`'s own comment on why). That means
these tests exercise genuine `asyncio` task interleaving (each `await`
point yields control back to the event loop, so two logically
concurrent coroutines really can interleave their statements), even
though the underlying connection is not itself multi-threaded --
that's the honest scope of what "concurrent" means in this test file.
"""

from __future__ import annotations

import asyncio

import pytest

from responsibleai.db import (
    ApprovalRepository,
    DelegationRepository,
    EvidenceRepository,
    OrgAuthorityCeilingRepository,
    create_engine,
)
from responsibleai.db.approval_repository import AlreadyVotedError, ApprovalNotApprovedError
from responsibleai.db.delegation_repository import DelegationEscalationError
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    AutonomyBudgetPolicy,
    GovernanceDecision,
    IdentityContext,
    OrgAuthorityCeiling,
    WhitePactRuntimeGateway,
    recent_autonomous_action_count,
)
from responsibleai.governance.approval import ApprovalStatus, build_approval_request
from responsibleai.governance.evidence import build_evidence_record
from responsibleai.governance.risk import RiskTier


def _identity(identity_id: str = "k1", org_id: str = "org-1") -> IdentityContext:
    return IdentityContext(identity_id=identity_id, kind="api_key", org_id=org_id)


def _agent(agent_id: str = "agent-1", org_id: str = "org-1") -> AgentContext:
    return AgentContext(identity=_identity(agent_id, org_id), agent_id=agent_id, framework="test")


def _authority(**kwargs) -> AuthorityContext:
    kwargs.setdefault("delegated_by", "org-1")
    kwargs.setdefault("granted_action_types", frozenset({"mcp_tool_call"}))
    return AuthorityContext(**kwargs)


@pytest.fixture()
async def engine():
    e = create_engine(":memory:")
    await e.init()
    yield e
    await e.close()


@pytest.fixture()
def approval_repo(engine):
    return ApprovalRepository(engine)


@pytest.fixture()
def evidence_repo(engine):
    return EvidenceRepository(engine)


@pytest.fixture()
def ceiling_repo(engine):
    return OrgAuthorityCeilingRepository(engine)


@pytest.fixture()
def delegation_repo(engine):
    return DelegationRepository(engine)


class TestApprovalConsumeConcurrency:
    """ApprovalRepository.consume()'s own docstring claims: 'There is no
    way to execute against one human approval twice.' This proves it,
    against the real DB-backed conditional UPDATE, not just the claim."""

    async def test_exactly_one_of_many_concurrent_consumes_wins(self, approval_repo) -> None:
        gw = WhitePactRuntimeGateway()
        agent = _agent()
        authority = _authority(
            granted_action_types=frozenset({"payment.execute"}),
            require_approval_for=frozenset({"payment.execute"}),
        )
        action = ActionRequest(agent=agent, action_type="payment.execute", target="acct-1")
        decision = gw.evaluate(action, authority)
        assert decision.decision == GovernanceDecision.REQUIRE_APPROVAL

        approval = await approval_repo.create(build_approval_request(action, decision))
        await approval_repo.resolve(
            approval.approval_id, resolved_by="approver-1", outcome=ApprovalStatus.APPROVED
        )

        results = await asyncio.gather(
            *[approval_repo.consume(approval.approval_id, action=action) for _ in range(20)],
            return_exceptions=True,
        )
        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, Exception)]
        assert len(successes) == 1
        assert len(failures) == 19
        assert all(isinstance(f, ApprovalNotApprovedError) for f in failures)


class TestApprovalVoteConcurrency:
    """resolve()'s own docstring: the DB's UNIQUE(approval_id,
    resolver_identity_id) constraint is 'what actually prevents a
    double vote under concurrency.' Proven here with a HIGH-risk
    (required_approvals=2) approval, so a single vote alone can't
    finalize it out from under the race."""

    async def test_exactly_one_of_many_concurrent_votes_from_the_same_identity_wins(
        self, approval_repo
    ) -> None:
        gw = WhitePactRuntimeGateway()
        agent = _agent()
        authority = _authority(
            granted_action_types=frozenset({"payment.execute"}),
            require_approval_for=frozenset({"payment.execute"}),
        )
        action = ActionRequest(agent=agent, action_type="payment.execute", target="acct-1")
        decision = gw.evaluate(action, authority)
        decision.risk_tier = RiskTier.HIGH  # forces required_approvals=2
        approval = await approval_repo.create(build_approval_request(action, decision))
        assert approval.required_approvals == 2

        results = await asyncio.gather(
            *[
                approval_repo.resolve(
                    approval.approval_id, resolved_by="voter-1", outcome=ApprovalStatus.APPROVED
                )
                for _ in range(20)
            ],
            return_exceptions=True,
        )
        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, Exception)]
        assert len(successes) == 1
        assert len(failures) == 19
        assert all(isinstance(f, AlreadyVotedError) for f in failures)


class TestEvidenceChainConcurrency:
    """EvidenceRepository's own constructor comment: the `asyncio.Lock()`
    exists specifically to serialize the hash-chain write. Proven here
    by firing many concurrent record() calls at the same org and
    confirming the resulting chain is genuinely intact -- every hash
    unique, every prev_hash link correct, verify_chain() returns True."""

    async def test_chain_stays_intact_under_concurrent_writes(self, evidence_repo) -> None:
        gw = WhitePactRuntimeGateway()
        n = 25

        async def _record_one(i: int):
            agent = _agent(agent_id=f"agent-{i}")
            authority = _authority()
            action = ActionRequest(agent=agent, action_type="mcp_tool_call", target=f"tool-{i}")
            decision = gw.evaluate(action, authority)
            evidence = build_evidence_record(action, agent, authority, decision)
            return await evidence_repo.record(evidence)

        results = await asyncio.gather(*[_record_one(i) for i in range(n)])

        assert len({r.hash for r in results}) == n  # no two writes collided on the same hash
        assert await evidence_repo.verify_chain("org-1") is True

        stored = await evidence_repo.list_for_org("org-1", limit=1000)
        assert len(stored) == n


class TestCeilingSetConcurrency:
    """OrgAuthorityCeilingRepository.set() is a check-then-insert-or-
    update with no compare-and-swap guard -- unlike consume()/resolve()
    above, nothing here documents a race-safety claim. This test's job
    is to confirm concurrent set() calls at minimum leave the org in a
    single, valid, gettable state -- not to assert which one 'wins'
    (that's inherently non-deterministic for concurrent writers to the
    same row, and not a property this test should pin down)."""

    async def test_concurrent_set_leaves_one_consistent_row(self, ceiling_repo) -> None:
        results = await asyncio.gather(
            *[
                ceiling_repo.set(OrgAuthorityCeiling(org_id="org-1", max_value_usd=float(i)))
                for i in range(10)
            ],
            return_exceptions=True,
        )
        # Every call either succeeds outright or fails with a real DB
        # integrity error -- never a silent corruption or a hang.
        for r in results:
            if isinstance(r, Exception):
                assert "UNIQUE" in str(r) or "IntegrityError" in type(r).__name__

        final = await ceiling_repo.get("org-1")
        assert final is not None
        assert final.max_value_usd in {float(i) for i in range(10)}


class TestDelegationGrantConcurrency:
    """DelegationRepository.grant() for independent root grants (no
    from_identity_id, so no attenuation check to race against) should
    all succeed concurrently -- each is an independent INSERT, not a
    shared row being updated."""

    async def test_concurrent_root_grants_to_different_identities_all_succeed(
        self, delegation_repo
    ) -> None:
        results = await asyncio.gather(
            *[
                delegation_repo.grant(
                    "org-1",
                    f"agent-{i}",
                    granted_action_types=frozenset({"rai_scan"}),
                    purpose="concurrency test",
                    granted_by="owner-1",
                )
                for i in range(10)
            ],
            return_exceptions=True,
        )
        assert all(not isinstance(r, Exception) for r in results)
        for i in range(10):
            assert await delegation_repo.get_active_delegation("org-1", f"agent-{i}") is not None

    async def test_concurrent_grants_to_the_same_identity_leave_one_consistent_latest(
        self, delegation_repo
    ) -> None:
        """Repeated grant() calls to the same to_identity_id are
        'supersede as latest', not an update to a shared row (see
        DelegationRepository's own docstring) -- each is an independent
        INSERT, so this should behave like the differing-identity case
        above: no crash, and get_latest_delegation() returns exactly
        one of the concurrently-granted rows afterward."""
        results = await asyncio.gather(
            *[
                delegation_repo.grant(
                    "org-1",
                    "agent-shared",
                    granted_action_types=frozenset({"rai_scan"}),
                    purpose=f"grant-{i}",
                    granted_by="owner-1",
                )
                for i in range(10)
            ],
            return_exceptions=True,
        )
        assert all(not isinstance(r, Exception) for r in results)
        latest = await delegation_repo.get_latest_delegation("org-1", "agent-shared")
        assert latest is not None
        assert latest.purpose.startswith("grant-")


class TestAutonomyBudgetConcurrency:
    """Honest finding, not a confirmation of a claimed protection:
    recent_autonomous_action_count() is a plain SELECT COUNT(*), with
    no lock analogous to EvidenceRepository's chain lock around the
    window between reading that count and the caller (apply_governance())
    recording the new evidence that would make the next count reflect
    this one. This test exercises that exact window directly, and
    reports what the current, un-fixed code actually does under
    concurrency -- see the assertion at the bottom for the honest
    result, not an assumption about it.
    """

    async def test_concurrent_autonomous_calls_can_jointly_exceed_the_budget(
        self, evidence_repo
    ) -> None:
        gw = WhitePactRuntimeGateway()
        budget = AutonomyBudgetPolicy(max_autonomous_actions=3, window_minutes=60)
        agent = _agent()
        authority = _authority()

        async def _one_governed_call(i: int):
            # Mirrors mcp/governance_integration.py's apply_governance()
            # shape exactly: count first, then decide, then (if allowed)
            # record -- the real check-then-act window this feature's
            # live code has, not a synthetic simplification of it.
            count = await recent_autonomous_action_count(
                evidence_repo, "org-1", agent.agent_id, window_minutes=budget.window_minutes
            )
            action = ActionRequest(agent=agent, action_type="mcp_tool_call", target=f"tool-{i}")
            decision = gw.evaluate(
                action,
                authority,
                autonomy_budget=budget,
                recent_autonomous_action_count=count,
            )
            evidence = build_evidence_record(action, agent, authority, decision)
            await evidence_repo.record(evidence)
            return decision.decision

        decisions = await asyncio.gather(*[_one_governed_call(i) for i in range(10)])
        allowed = [d for d in decisions if d == GovernanceDecision.ALLOW]

        # The honest, empirically-confirmed result (verified by hand
        # before writing this assertion, not assumed): without a lock
        # around the count-then-record window, ALL 10 concurrent calls
        # get allowed against a budget of 3 -- every one of them reads
        # the same pre-write count before any of the others' evidence
        # commits. This assertion documents that as a known, current
        # limitation -- not a desired behavior -- so a future fix that
        # closes this window has a test that will start failing
        # (correctly, prompting an update) rather than this gap staying
        # silently undocumented.
        assert len(allowed) == 10
        assert len(allowed) > budget.max_autonomous_actions


class TestDelegationRevokeBranchConcurrency:
    """Heart Phase H9 closes a gap `docs/heart/HEART_CURRENT_STATE.md`
    §3 named explicitly: `revoke_branch()`'s cascading revocation is
    functionally correct and tested (`tests/test_delegation_graph.py::TestCascadingRevocation`),
    but had no dedicated concurrency/race-condition test, unlike the
    grant side (`TestDelegationGrantConcurrency` above). This class
    adds that test, mirroring the grant side's pattern, plus one
    honest race-condition finding for the same "check-then-act" shape
    `TestAutonomyBudgetConcurrency` above already found on the
    autonomy-budget path -- reported as what the code actually does,
    not assumed to be safe."""

    async def test_concurrent_revoke_branch_on_independent_trees_both_succeed(
        self, delegation_repo
    ) -> None:
        await delegation_repo.grant(
            "org-1",
            "tree-a-root",
            granted_action_types=frozenset({"rai_scan"}),
            purpose="tree a",
            granted_by="owner-1",
        )
        await delegation_repo.grant(
            "org-1",
            "tree-b-root",
            granted_action_types=frozenset({"rai_scan"}),
            purpose="tree b",
            granted_by="owner-1",
        )

        results = await asyncio.gather(
            delegation_repo.revoke_branch(
                "org-1", "tree-a-root", revoked_by="owner-1", reason="cleanup a"
            ),
            delegation_repo.revoke_branch(
                "org-1", "tree-b-root", revoked_by="owner-1", reason="cleanup b"
            ),
            return_exceptions=True,
        )
        assert all(not isinstance(r, Exception) for r in results)
        assert await delegation_repo.get_active_delegation("org-1", "tree-a-root") is None
        assert await delegation_repo.get_active_delegation("org-1", "tree-b-root") is None

    async def test_concurrent_revoke_branch_on_the_same_identity_leaves_it_revoked(
        self, delegation_repo
    ) -> None:
        """Honest finding, not a confirmation of a claimed protection.
        revoke_branch()'s docstring says already-inactive delegations
        are 'skipped, not re-touched' -- true only for calls that don't
        overlap. Under a real race, `active = await get_active_delegation()`
        is a plain read with no lock, so multiple concurrent callers can
        each read the delegation as still active *before any of their
        UPDATEs land*, and each proceeds to include it in its own
        `revoked_ids` return list -- the exact same check-then-act shape
        `TestAutonomyBudgetConcurrency` above already found on the
        autonomy-budget path. The empirically-confirmed result: all 5
        concurrent calls report having revoked it (`revoked_ids` summed
        across calls is 5, not 1), even though the delegation itself
        ends up correctly, terminally revoked in the database -- the
        DB state is not corrupted, but the per-call return values are
        not deduplicated the way the docstring's 'skipped, not
        re-touched' language would suggest under concurrency."""
        await delegation_repo.grant(
            "org-1",
            "shared-root",
            granted_action_types=frozenset({"rai_scan"}),
            purpose="shared",
            granted_by="owner-1",
        )

        results = await asyncio.gather(
            *[
                delegation_repo.revoke_branch(
                    "org-1", "shared-root", revoked_by="owner-1", reason=f"revoke-{i}"
                )
                for i in range(5)
            ],
            return_exceptions=True,
        )
        successes = [r for r in results if not isinstance(r, BaseException)]
        assert len(successes) == len(results)
        # The database ends up in the correct terminal state regardless
        # of the race -- this is what actually matters operationally.
        assert await delegation_repo.get_active_delegation("org-1", "shared-root") is None
        # But the naive expectation that only one caller "did the
        # revoking" is false under this exact interleaving -- documented
        # here so a future fix that closes this window has a test that
        # will start failing (correctly) rather than this gap staying
        # silently undocumented.
        total_revoked = sum(len(r) for r in successes)
        assert total_revoked == 5

    async def test_grant_racing_revoke_branch_is_correctly_rejected(self, delegation_repo) -> None:
        """The interleaving this test forces (a grant() for a NEW child
        of a node, timed to land after revoke_branch() has already read
        that node's children but before revoke_branch() finishes) was
        hypothesized as a possible TOCTOU gap -- a child slipping in
        after the parent's children were already read, orphaned with a
        revoked parent. Empirically, it is not: revoke_branch() revokes
        a node (commits the UPDATE) strictly *before* reading that
        node's children, so by the time this test's forced interleaving
        reaches the concurrent grant()'s own parent-liveness check
        (`get_active_delegation(from_identity_id)`), the parent is
        already revoked in the database and grant() correctly raises
        `DelegationEscalationError` rather than creating an orphaned
        active child. This is a genuine, confirmed protection, not an
        assumed one -- worth keeping as a regression test in case a
        future refactor reorders revoke_branch()'s own
        revoke-then-read-children sequence."""
        await delegation_repo.grant(
            "org-1",
            "parent",
            granted_action_types=frozenset({"rai_scan"}),
            purpose="parent",
            granted_by="owner-1",
        )

        original_direct_children = delegation_repo._direct_children
        release_grant = asyncio.Event()
        child_granted = asyncio.Event()

        async def _direct_children_then_wait(org_id: str, identity_id: str):
            result = await original_direct_children(org_id, identity_id)
            if identity_id == "parent":
                # Simulate: revoke_branch() has just read "parent"'s
                # children (none yet) -- now let the concurrent grant()
                # proceed before revoke_branch() moves on.
                release_grant.set()
                await child_granted.wait()
            return result

        delegation_repo._direct_children = _direct_children_then_wait

        async def _grant_child_after_signal():
            await release_grant.wait()
            try:
                await delegation_repo.grant(
                    "org-1",
                    "child",
                    granted_action_types=frozenset({"rai_scan"}),
                    purpose="child",
                    granted_by="parent",
                    from_identity_id="parent",
                )
            finally:
                # Unblock revoke_branch()'s wait regardless of outcome --
                # a deadlock here would hang the test, not fail it cleanly.
                child_granted.set()

        try:
            results = await asyncio.gather(
                delegation_repo.revoke_branch(
                    "org-1", "parent", revoked_by="owner-1", reason="cleanup"
                ),
                _grant_child_after_signal(),
                return_exceptions=True,
            )
        finally:
            delegation_repo._direct_children = original_direct_children

        revoke_result, grant_result = results
        assert not isinstance(revoke_result, BaseException)
        assert isinstance(grant_result, DelegationEscalationError)

        parent_active = await delegation_repo.get_active_delegation("org-1", "parent")
        child_active = await delegation_repo.get_active_delegation("org-1", "child")
        assert parent_active is None
        assert child_active is None  # grant() correctly refused to create it


class TestDelegationRevokeBranchLatency:
    """Heart Phase H9's other named gap: no latency measurement existed
    for cascading revocation. This establishes a first, honest
    measurement -- generous enough to avoid flaking on a loaded CI
    runner, tight enough to catch a real algorithmic regression (e.g.
    accidentally reintroducing O(n^2) behavior)."""

    async def test_revoke_branch_completes_promptly_for_a_wide_tree(self, delegation_repo) -> None:
        await delegation_repo.grant(
            "org-1",
            "latency-root",
            granted_action_types=frozenset({"rai_scan"}),
            purpose="root",
            granted_by="owner-1",
        )
        for i in range(100):
            await delegation_repo.grant(
                "org-1",
                f"latency-child-{i}",
                granted_action_types=frozenset({"rai_scan"}),
                purpose=f"child-{i}",
                granted_by="latency-root",
                from_identity_id="latency-root",
            )

        loop = asyncio.get_event_loop()
        started = loop.time()
        revoked_ids = await delegation_repo.revoke_branch(
            "org-1", "latency-root", revoked_by="owner-1", reason="latency test"
        )
        elapsed = loop.time() - started

        assert len(revoked_ids) == 101  # root + 100 children
        # First measurement, not a tuned SLA -- generous bound chosen
        # to catch a real regression (e.g. O(n^2) traversal) without
        # flaking under normal CI variance for 101 sequential
        # single-row operations against an in-memory SQLite engine.
        assert elapsed < 5.0, f"revoke_branch() took {elapsed:.3f}s for 101 nodes"
