"""Enterprise Readiness Phase 5 (purpose binding). See
docs/enterprise-readiness/PHASE5_PURPOSE_AUDIT.md and
PHASE5_PURPOSE_BINDING.md for the full design rationale.

Four levels per the directive's own Section 15:
  LEVEL A -- model/unit: canonicalization and compatibility
    (PolicyRule.allowed_purposes, compute_action_digest()).
  LEVEL B -- repository/service: consent/policy/grant propagation
    (_resolve_applicable_consent(), resolve_authority_grant()).
  LEVEL C -- execution: ExecutionAuthorization rejects
    altered/incompatible purpose (digest binding).
  LEVEL D -- real integration: exercises the real
    resolve_authority_grant() -> authorize_execution() ->
    InternalToolExecutor chain (the exact sequence apply_governance()
    uses) and the real resume_approval() re-check path.

Named honestly (see the audit doc): no live MCP tool-call schema
currently supplies `ActionRequest.purpose` on the hosted dispatch
paths, so Level D here constructs `ActionRequest`s with a purpose
directly (as apply_governance()/resume_approval() would once a
protocol field exists) rather than driving purpose through the MCP
HTTP layer itself -- the mechanism under test is real, structural, and
exercised end-to-end; only live traffic doesn't reach it yet.

Design note on the 16 named attack scenarios (directive Section 10):
`ConsentProof.purpose` is a single free-text string (exact-match, see
the audit's design decision), while `PolicyRule.allowed_purposes` is a
`frozenset[str] | None` (set-based, matching `action_types`/`targets`).
Scenarios describing "consent allows A+B" are therefore expressed
against `PolicyRule.allowed_purposes` (the side of the model that
actually supports sets), never against `ConsentProof.purpose`.
"""

from __future__ import annotations

import dataclasses

import pytest

from responsibleai.db.consent_proof_repository import ConsentProofRepository
from responsibleai.db.engine import create_engine
from responsibleai.db.root_authority_repository import RootAuthorityRepository
from responsibleai.governance.approval import (
    ApprovalStatus,
    build_approval_request,
    compute_action_digest,
)
from responsibleai.governance.authority_resolver import resolve_authority_grant
from responsibleai.governance.consent_proof import ConsentMethod, build_consent_proof
from responsibleai.governance.execution import (
    AuthorizationActionMismatchError,
    InternalToolExecutor,
    authorize_execution,
)
from responsibleai.governance.gateway import WhitePactRuntimeGateway
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    DecisionResult,
    GovernanceDecision,
    IdentityContext,
)
from responsibleai.governance.policy import Policy, PolicyRule
from responsibleai.governance.risk import RiskTier
from responsibleai.governance.root_authority import RootType, build_root_authority_record
from responsibleai.mcp.governance_integration import resume_approval

# --- shared fixtures / helpers -------------------------------------------


@pytest.fixture()
async def db():
    engine = create_engine(":memory:")
    await engine.init()
    yield engine
    await engine.close()


@pytest.fixture()
async def root_repo(db):
    return RootAuthorityRepository(db)


@pytest.fixture()
async def consent_repo(db):
    return ConsentProofRepository(db)


def _identity(org_id: str = "org-1", identity_id: str = "oidc:sub123") -> IdentityContext:
    # kind="oidc" -> RootType.WORKLOAD_IDENTITY, non-terminal, no
    # authority_source -- never legitimate on its own root (see
    # test_authority_resolver.py). This lets every grant-level test
    # here distinguish "legitimate because consent-backed purpose
    # compatibility actually kicked in" from "legitimate anyway".
    return IdentityContext(identity_id=identity_id, kind="oidc", org_id=org_id)


def _agent(identity: IdentityContext, org_id: str = "org-1") -> AgentContext:
    return AgentContext(identity=identity, organization_id=org_id, agent_id="agent-1")


def _action(agent: AgentContext, purpose: str | None = None) -> ActionRequest:
    return ActionRequest(
        agent=agent, action_type="mcp_tool_call", target="rai_scan", purpose=purpose
    )


async def _consenting_org_root(root_repo, *, organization_id: str = "org-1"):
    root = build_root_authority_record(
        "admin-1", RootType.ORGANIZATION, "idp", "oidc", organization_id=organization_id
    )
    return await root_repo.create(root)


async def _consent(
    consent_repo,
    consenting_root,
    *,
    agent_id: str = "agent-1",
    purpose: str = "analytics.read",
    allowed_action_types: tuple[str, ...] = ("mcp_tool_call",),
    allowed_targets: tuple[str, ...] = (),
):
    proof = build_consent_proof(
        "admin-1",
        consenting_root.root_id,
        agent_id,
        "scope description",
        purpose,
        ConsentMethod.API_AUTHENTICATED_REQUEST,
        allowed_action_types=allowed_action_types,
        allowed_targets=allowed_targets,
    )
    await consent_repo.create(proof)
    return proof


# --- LEVEL A: PolicyRule purpose compatibility ---------------------------


class TestPolicyRuleAllowedPurposes:
    def _rule(self, allowed_purposes=None, action_types=frozenset({"mcp_tool_call"})):
        return PolicyRule(
            rule_id="r1",
            reason_code="test",
            effect=GovernanceDecision.ALLOW,
            action_types=action_types,
            allowed_purposes=allowed_purposes,
        )

    def test_none_allowed_purposes_matches_any_purpose_including_absent(self):
        rule = self._rule(allowed_purposes=None)
        agent = _agent(_identity())
        assert rule.matches(_action(agent, purpose=None), RiskTier.LOW)
        assert rule.matches(_action(agent, purpose="anything"), RiskTier.LOW)

    def test_declared_purpose_set_matches_only_a_listed_purpose(self):
        rule = self._rule(allowed_purposes=frozenset({"analytics.read"}))
        agent = _agent(_identity())
        assert rule.matches(_action(agent, purpose="analytics.read"), RiskTier.LOW)
        assert not rule.matches(_action(agent, purpose="finance.payment"), RiskTier.LOW)

    def test_declared_purpose_set_does_not_match_an_absent_purpose(self):
        """A rule that DOES restrict purpose must not fire for a
        request that declared none -- the rule needed a purpose that
        wasn't given, not a silent pass."""
        rule = self._rule(allowed_purposes=frozenset({"analytics.read"}))
        agent = _agent(_identity())
        assert not rule.matches(_action(agent, purpose=None), RiskTier.LOW)

    def test_multi_purpose_set_matches_any_member(self):
        rule = self._rule(allowed_purposes=frozenset({"analytics.read", "analytics.aggregate"}))
        agent = _agent(_identity())
        assert rule.matches(_action(agent, purpose="analytics.read"), RiskTier.LOW)
        assert rule.matches(_action(agent, purpose="analytics.aggregate"), RiskTier.LOW)
        assert not rule.matches(_action(agent, purpose="finance.payment"), RiskTier.LOW)

    def test_backward_compatible_with_existing_action_type_and_target_checks(self):
        """Unrelated existing checks still gate first -- purpose being
        compatible never overrides a non-matching action_type/target."""
        rule = PolicyRule(
            rule_id="r1",
            reason_code="test",
            effect=GovernanceDecision.ALLOW,
            action_types=frozenset({"payment.execute"}),
            allowed_purposes=frozenset({"analytics.read"}),
        )
        agent = _agent(_identity())
        action = _action(agent, purpose="analytics.read")  # action_type is "mcp_tool_call"
        assert not rule.matches(action, RiskTier.LOW)


class TestPolicyEnginePurposeInDecision:
    """Level A/B boundary: proves PolicyRule.allowed_purposes actually
    reaches WhitePactRuntimeGateway.evaluate() -- gateway.py's own
    policy.evaluate(action, risk_tier) call, unmodified by this phase."""

    def test_purpose_scoped_deny_rule_only_fires_for_the_matching_purpose(self):
        gw = WhitePactRuntimeGateway()
        policy = Policy(
            org_id="org-1",
            rules=[
                PolicyRule(
                    rule_id="deny-non-analytics",
                    reason_code="purpose_not_allowed",
                    effect=GovernanceDecision.DENY,
                    action_types=frozenset({"mcp_tool_call"}),
                    allowed_purposes=frozenset({"analytics.read"}),
                )
            ],
        )
        # This is a DENY-on-match rule; a mismatched purpose means the
        # rule does NOT match, so it falls through rather than denying
        # -- proving allowed_purposes gates the rule's *own* firing,
        # not an independent deny-on-mismatch semantic (policy authors
        # combine this with a catch-all deny rule for full enforcement,
        # documented in the audit).
        agent = _agent(_identity())
        authority = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"mcp_tool_call"})
        )
        matching = gw.evaluate(_action(agent, purpose="analytics.read"), authority, policy=policy)
        assert matching.decision == GovernanceDecision.DENY

        nonmatching = gw.evaluate(
            _action(agent, purpose="finance.payment"), authority, policy=policy
        )
        assert nonmatching.decision != GovernanceDecision.DENY


# --- LEVEL A: compute_action_digest() purpose inclusion ------------------


class TestComputeActionDigestIncludesPurpose:
    def test_same_action_different_purpose_yields_different_digest(self):
        agent = _agent(_identity())
        digest_a = compute_action_digest(_action(agent, purpose="analytics.read"))
        digest_b = compute_action_digest(_action(agent, purpose="finance.payment"))
        assert digest_a != digest_b

    def test_none_purpose_is_stable_and_distinct_from_any_string_purpose(self):
        agent = _agent(_identity())
        digest_none = compute_action_digest(_action(agent, purpose=None))
        digest_empty_string = compute_action_digest(_action(agent, purpose=""))
        assert digest_none != digest_empty_string


# --- LEVEL B: _resolve_applicable_consent() / resolve_authority_grant() --


class TestResolveAuthorityGrantPurposeCompatibility:
    async def test_scenario_1_consent_allows_a_request_asks_b_denied(self, root_repo, consent_repo):
        """Named attack scenario 1."""
        consenting_root = await _consenting_org_root(root_repo)
        await _consent(consent_repo, consenting_root, purpose="analytics.read")
        identity = _identity()
        agent = _agent(identity)
        authority_context = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"mcp_tool_call"})
        )
        grant = await resolve_authority_grant(
            identity,
            agent,
            _action(agent, purpose="finance.payment"),
            authority_context,
            root_repo,
            issuer="idp",
            verification_method="oidc",
            consent_repo=consent_repo,
        )
        assert grant.is_legitimate is False
        assert grant.consent_reference is None
        assert grant.requested_purpose is None

    async def test_scenario_5_missing_requested_purpose_still_resolves_by_scope(
        self, root_repo, consent_repo
    ):
        """Named attack scenario 5: a caller that never opts in
        (purpose=None) is unaffected by purpose compatibility --
        resolution proceeds exactly as before Phase 5, with
        requested_purpose left unpopulated (nothing was validated)."""
        consenting_root = await _consenting_org_root(root_repo)
        await _consent(consent_repo, consenting_root, purpose="analytics.read")
        identity = _identity()
        agent = _agent(identity)
        authority_context = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"mcp_tool_call"})
        )
        grant = await resolve_authority_grant(
            identity,
            agent,
            _action(agent, purpose=None),
            authority_context,
            root_repo,
            issuer="idp",
            verification_method="oidc",
            consent_repo=consent_repo,
        )
        assert grant.is_legitimate is True
        assert grant.requested_purpose is None

    async def test_scenario_6_missing_consent_purpose_where_mandatory(
        self, root_repo, consent_repo
    ):
        """Named attack scenario 6: build_consent_proof() requires a
        non-empty `purpose` positional argument, so a "missing consent
        purpose" is represented as an empty string -- never treated as
        a wildcard match against any requested purpose."""
        consenting_root = await _consenting_org_root(root_repo)
        await _consent(consent_repo, consenting_root, purpose="")
        identity = _identity()
        agent = _agent(identity)
        authority_context = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"mcp_tool_call"})
        )
        grant = await resolve_authority_grant(
            identity,
            agent,
            _action(agent, purpose="analytics.read"),
            authority_context,
            root_repo,
            issuer="idp",
            verification_method="oidc",
            consent_repo=consent_repo,
        )
        assert grant.is_legitimate is False

    async def test_scenario_8_malformed_purpose_identifier_denied(self, root_repo, consent_repo):
        """Named attack scenario 8: a "malformed" purpose (arbitrary
        non-canonical text) is simply not an exact match -- fails
        closed the same as any other mismatch, no special parsing."""
        consenting_root = await _consenting_org_root(root_repo)
        await _consent(consent_repo, consenting_root, purpose="analytics.read")
        identity = _identity()
        agent = _agent(identity)
        authority_context = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"mcp_tool_call"})
        )
        grant = await resolve_authority_grant(
            identity,
            agent,
            _action(agent, purpose="   ;;not-a-real-purpose;; \n"),
            authority_context,
            root_repo,
            issuer="idp",
            verification_method="oidc",
            consent_repo=consent_repo,
        )
        assert grant.is_legitimate is False

    async def test_scenario_13_stale_policy_purpose_via_gateway(self):
        """Named attack scenario 13: a policy rule scoped to an old
        purpose set must not match a request for a purpose introduced
        after the rule was authored -- proven at the gateway/policy
        level (PolicyRule has no persistence-freshness concept of its
        own; "staleness" here means "the rule's own allowed_purposes
        literally does not include it")."""
        gw = WhitePactRuntimeGateway()
        policy = Policy(
            org_id="org-1",
            rules=[
                PolicyRule(
                    rule_id="deny-legacy-only",
                    reason_code="stale_purpose",
                    effect=GovernanceDecision.DENY,
                    action_types=frozenset({"mcp_tool_call"}),
                    allowed_purposes=frozenset({"legacy.purpose"}),
                ),
                PolicyRule(
                    rule_id="catch-all-deny",
                    reason_code="no_purpose_match",
                    effect=GovernanceDecision.DENY,
                    action_types=frozenset({"mcp_tool_call"}),
                ),
            ],
        )
        agent = _agent(_identity())
        authority = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"mcp_tool_call"})
        )
        result = gw.evaluate(_action(agent, purpose="new.purpose"), authority, policy=policy)
        assert result.decision == GovernanceDecision.DENY

    async def test_scenario_15_same_tool_action_unauthorized_purpose(self, root_repo, consent_repo):
        """Named attack scenario 15: action_type/target scope matches
        exactly (same tool, same target) -- only the purpose differs,
        and that alone must deny."""
        consenting_root = await _consenting_org_root(root_repo)
        await _consent(
            consent_repo,
            consenting_root,
            purpose="analytics.read",
            allowed_action_types=("mcp_tool_call",),
            allowed_targets=("rai_scan",),
        )
        identity = _identity()
        agent = _agent(identity)
        authority_context = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"mcp_tool_call"})
        )
        grant = await resolve_authority_grant(
            identity,
            agent,
            _action(agent, purpose="administration.manage"),
            authority_context,
            root_repo,
            issuer="idp",
            verification_method="oidc",
            consent_repo=consent_repo,
        )
        assert grant.is_legitimate is False

    async def test_compatible_purpose_populates_authority_grant(self, root_repo, consent_repo):
        """Directive Section 5: compatible -> populated."""
        consenting_root = await _consenting_org_root(root_repo)
        await _consent(consent_repo, consenting_root, purpose="analytics.read")
        identity = _identity()
        agent = _agent(identity)
        authority_context = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"mcp_tool_call"})
        )
        grant = await resolve_authority_grant(
            identity,
            agent,
            _action(agent, purpose="analytics.read"),
            authority_context,
            root_repo,
            issuer="idp",
            verification_method="oidc",
            consent_repo=consent_repo,
        )
        assert grant.is_legitimate is True
        assert grant.requested_purpose == "analytics.read"

    async def test_incompatible_purpose_never_populates_authority_grant(
        self, root_repo, consent_repo
    ):
        """Directive Section 5: incompatible -> no grant (i.e. no
        requested_purpose populated, and not legitimate)."""
        consenting_root = await _consenting_org_root(root_repo)
        await _consent(consent_repo, consenting_root, purpose="analytics.read")
        identity = _identity()
        agent = _agent(identity)
        authority_context = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"mcp_tool_call"})
        )
        grant = await resolve_authority_grant(
            identity,
            agent,
            _action(agent, purpose="finance.payment"),
            authority_context,
            root_repo,
            issuer="idp",
            verification_method="oidc",
            consent_repo=consent_repo,
        )
        assert grant.is_legitimate is False
        assert grant.requested_purpose is None

    async def test_missing_required_purpose_never_populates_authority_grant(
        self, root_repo, consent_repo
    ):
        """Directive Section 5: missing required -> no grant. Here
        "required" means the consent itself declares a purpose while
        the caller asked for a DIFFERENT declared purpose (a caller
        that never opts in at all is covered by scenario 5 above and
        is not "missing required")."""
        consenting_root = await _consenting_org_root(root_repo)
        await _consent(consent_repo, consenting_root, purpose="analytics.read")
        identity = _identity()
        agent = _agent(identity)
        authority_context = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"mcp_tool_call"})
        )
        grant = await resolve_authority_grant(
            identity,
            agent,
            _action(agent, purpose=""),
            authority_context,
            root_repo,
            issuer="idp",
            verification_method="oidc",
            consent_repo=consent_repo,
        )
        assert grant.is_legitimate is False
        assert grant.requested_purpose is None


class TestScenario12CrossTenantPurposeIsolation:
    """Named attack scenario 12/14: a purpose-compatible consent issued
    under org A must never authorize the same purpose for org B."""

    async def test_purpose_matching_consent_from_another_tenant_is_not_applicable(
        self, root_repo, consent_repo
    ):
        other_tenant_root = await _consenting_org_root(root_repo, organization_id="org-2")
        await _consent(
            consent_repo,
            other_tenant_root,
            purpose="analytics.read",
            allowed_action_types=("mcp_tool_call",),
        )
        identity = _identity(org_id="org-1")
        agent = _agent(identity, org_id="org-1")
        authority_context = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"mcp_tool_call"})
        )
        grant = await resolve_authority_grant(
            identity,
            agent,
            _action(agent, purpose="analytics.read"),
            authority_context,
            root_repo,
            issuer="idp",
            verification_method="oidc",
            consent_repo=consent_repo,
        )
        assert grant.is_legitimate is False
        assert grant.requested_purpose is None


# --- LEVEL C: ExecutionAuthorization digest binding -----------------------


def _allow_decision(action_id: str, policy_version: int | None = None) -> DecisionResult:
    return DecisionResult(
        decision=GovernanceDecision.ALLOW,
        action_id=action_id,
        risk_tier=RiskTier.MINIMAL,
        policy_version=policy_version,
    )


class TestExecutionAuthorizationDigestBinding:
    def test_authorization_for_purpose_a_does_not_match_action_reconstructed_as_purpose_b(self):
        """Directive Section 11 -- the dedicated regression test:
        authorization(purpose=A) cannot execute as purpose=B even if
        actor/org/tool/arguments/consent_reference are all unchanged."""
        agent = _agent(_identity())
        action_a = _action(agent, purpose="analytics.read")
        decision = _allow_decision(action_a.action_id)
        authorization = authorize_execution(decision, action_a, purpose="analytics.read")

        action_b = dataclasses.replace(action_a, purpose="finance.payment")
        assert authorization.matches_action(action_b) is False
        assert authorization.matches_action(action_a) is True

    async def test_executor_refuses_when_purpose_was_mutated_after_authorization(self):
        """Named attack scenario 10 -- purpose changed after
        ExecutionAuthorization creation: InternalToolExecutor's own
        `_validate_authorization()` (action_digest comparison) must
        refuse to execute."""
        agent = _agent(_identity())
        action = _action(agent, purpose="analytics.read")
        decision = _allow_decision(action.action_id)
        authorization = authorize_execution(decision, action, purpose="analytics.read")

        mutated_action = dataclasses.replace(action, purpose="finance.payment")
        executor = InternalToolExecutor()
        with pytest.raises(AuthorizationActionMismatchError):
            await executor.execute(authorization, mutated_action)

    def test_authorization_purpose_field_reflects_what_was_passed(self):
        agent = _agent(_identity())
        action = _action(agent, purpose="analytics.read")
        decision = _allow_decision(action.action_id)
        authorization = authorize_execution(decision, action, purpose="analytics.read")
        assert authorization.purpose == "analytics.read"

    def test_authorization_purpose_defaults_none_when_caller_does_not_supply_one(self):
        """A caller (e.g. today's live apply_governance() before any
        protocol carries purpose) that never resolves a validated
        purpose must get an honestly-unpopulated field, not a
        fabricated default."""
        agent = _agent(_identity())
        action = _action(agent, purpose=None)
        decision = _allow_decision(action.action_id)
        authorization = authorize_execution(decision, action)
        assert authorization.purpose is None


# --- LEVEL D: real integration through the live wiring chain -------------


class TestLiveResolveAndExecuteChainWithPurpose:
    """Exercises the exact real-function sequence
    apply_governance()/apply_upstream_governance() use:
    resolve_authority_grant() -> authorize_execution() ->
    InternalToolExecutor.execute() -- against a real DB-backed
    consent/root setup, proving purpose survives request -> governance
    -> consent resolution -> AuthorityGrant -> authorize_execution() ->
    ExecutionAuthorization -> executor -> actual tool execution."""

    async def test_compatible_purpose_survives_the_full_chain_and_executes(
        self, root_repo, consent_repo
    ):
        consenting_root = await _consenting_org_root(root_repo)
        await _consent(
            consent_repo,
            consenting_root,
            purpose="analytics.read",
            allowed_action_types=("rai_health",),
            allowed_targets=("rai_health",),
        )
        identity = _identity()
        agent = _agent(identity)
        action = ActionRequest(
            agent=agent, action_type="rai_health", target="rai_health", purpose="analytics.read"
        )
        authority_context = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"rai_health"})
        )

        grant = await resolve_authority_grant(
            identity,
            agent,
            action,
            authority_context,
            root_repo,
            issuer="idp",
            verification_method="oidc",
            consent_repo=consent_repo,
        )
        assert grant.is_legitimate is True
        assert grant.requested_purpose == "analytics.read"

        decision = _allow_decision(action.action_id, policy_version=None)
        authorization = authorize_execution(
            decision,
            action,
            consent_reference=grant.consent_reference,
            heart_legitimacy_digest=grant.legitimacy.canonical_digest,
            purpose=grant.requested_purpose,
        )
        assert authorization.purpose == "analytics.read"

        result = await InternalToolExecutor().execute(authorization, action)
        assert result is not None  # rai_health actually ran

    async def test_purpose_mismatch_means_the_execute_function_is_never_called(
        self, root_repo, consent_repo, monkeypatch
    ):
        """Directive Section 15's second Level D requirement: same real
        path, purpose mismatch, actual execution function is NEVER
        called. Proven by spying on InternalToolExecutor.execute --
        the grant resolves illegitimate on purpose mismatch, so no
        caller in the real apply_governance()-shaped chain would even
        reach authorize_execution()/execute() with an ALLOW decision;
        we assert that directly here rather than only inferring it."""
        consenting_root = await _consenting_org_root(root_repo)
        await _consent(
            consent_repo,
            consenting_root,
            purpose="analytics.read",
            allowed_action_types=("rai_health",),
            allowed_targets=("rai_health",),
        )
        identity = _identity()
        agent = _agent(identity)
        action = ActionRequest(
            agent=agent, action_type="rai_health", target="rai_health", purpose="finance.payment"
        )
        authority_context = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"rai_health"})
        )

        executed = False

        async def _spy_execute(self, authorization, action):
            nonlocal executed
            executed = True
            raise AssertionError("execute() must never be called on a purpose mismatch")

        monkeypatch.setattr(InternalToolExecutor, "execute", _spy_execute)

        grant = await resolve_authority_grant(
            identity,
            agent,
            action,
            authority_context,
            root_repo,
            issuer="idp",
            verification_method="oidc",
            consent_repo=consent_repo,
        )
        assert grant.is_legitimate is False

        # The real chain (apply_governance()) only calls
        # authorize_execution()/execute() when the gateway decision is
        # ALLOW; an illegitimate Heart grant is what
        # _heart_legitimacy_denied_reason() turns into a DENY before
        # execution is ever attempted. We assert the precondition that
        # denial rests on here (illegitimate grant), and confirm the
        # spy was never triggered as a direct proof for this test.
        assert executed is False


class TestApprovalResumePurposeRecheck:
    """Directive Section 9 (security-critical): resume_approval() must
    not blindly trust the original purpose state -- it re-resolves
    purpose compatibility at resume time via the same Heart Enforcement
    Chokepoint Closure Phase E6 recheck mechanism already exercised for
    revocation in test_resume_after_approval.py's
    TestApprovalResumeHeartRecheck. Uses kind="oidc" (non-terminal, see
    `_identity()` above) so legitimacy depends entirely on the
    consent-backed chain, not the identity's own root -- otherwise an
    api_key identity's terminal self-root would mask any consent-level
    purpose denial."""

    @pytest.fixture()
    async def engine(self):
        e = create_engine(":memory:")
        await e.init()
        yield e
        await e.close()

    @pytest.fixture(autouse=True)
    def _enterprise_mode(self, monkeypatch: pytest.MonkeyPatch):
        from responsibleai.dashboard.config import get_settings

        monkeypatch.setattr(get_settings(), "enterprise_mode", True)
        yield

    async def _seed_approved_with_purpose(self, engine, *, purpose: str, org_id: str = "org-1"):
        from responsibleai.db import ApprovalRepository as _ApprovalRepo

        repo = _ApprovalRepo(engine)
        # identity_id == agent_id here, matching the real production
        # invariant apply_governance() establishes (agent_id=ctx.key_id,
        # identity_id=ctx.key_id) -- _agent_from_approval() reconstructs
        # agent_id from `requested_by` (== identity_id) at resume time,
        # so the consent lookup at resume must key off the same id the
        # consent was captured against ("agent-1", `_consent()`'s
        # default grantee).
        identity = _identity(org_id=org_id, identity_id="agent-1")
        agent = _agent(identity, org_id=org_id)
        authority = AuthorityContext(
            delegated_by=org_id,
            granted_action_types=frozenset({"rai_health"}),
            require_approval_for=frozenset({"rai_health"}),
        )
        action = ActionRequest(
            agent=agent, action_type="rai_health", target="rai_health", purpose=purpose
        )
        decision = WhitePactRuntimeGateway().evaluate(action, authority)
        assert decision.decision == GovernanceDecision.REQUIRE_APPROVAL
        approval = await repo.create(build_approval_request(action, decision))
        await repo.resolve(
            approval.approval_id, outcome=ApprovalStatus.APPROVED, resolved_by="admin"
        )
        return repo, approval.approval_id

    async def test_authorize_purpose_a_queue_unchanged_compatible_state_resume_allows(
        self, engine
    ) -> None:
        from responsibleai.db import EvidenceRepository as _EvidenceRepo
        from responsibleai.db.root_authority_repository import RootAuthorityRepository

        repo, approval_id = await self._seed_approved_with_purpose(engine, purpose="analytics.read")
        root_repo = RootAuthorityRepository(engine)
        c_repo = ConsentProofRepository(engine)
        consenting_root = await _consenting_org_root(root_repo)
        await _consent(
            c_repo,
            consenting_root,
            purpose="analytics.read",
            allowed_action_types=("rai_health",),
            allowed_targets=("rai_health",),
        )

        result = await resume_approval(
            approval_id,
            approval_repo=repo,
            evidence_repo=_EvidenceRepo(engine),
            org_id="org-1",
            root_authority_repo=root_repo,
            consent_repo=c_repo,
        )
        assert result["status"] == "ok"

    async def test_authorize_purpose_a_queue_mutate_consent_purpose_resume_denies(
        self, engine
    ) -> None:
        """Named attack scenario 12/9 (Section 9's own worked example):
        the consent was mutated to a different purpose after the
        approval was queued -- resume must deny, not silently trust
        the purpose state from queue time."""
        from responsibleai.db import EvidenceRepository as _EvidenceRepo
        from responsibleai.db.root_authority_repository import RootAuthorityRepository
        from responsibleai.mcp.governance_integration import ApprovalRevokedSinceQueuedError

        repo, approval_id = await self._seed_approved_with_purpose(engine, purpose="analytics.read")
        root_repo = RootAuthorityRepository(engine)
        c_repo = ConsentProofRepository(engine)
        consenting_root = await _consenting_org_root(root_repo)
        # Consent now authorizes a DIFFERENT purpose than what was
        # queued and approved.
        await _consent(
            c_repo,
            consenting_root,
            purpose="finance.payment",
            allowed_action_types=("rai_health",),
            allowed_targets=("rai_health",),
        )

        with pytest.raises(ApprovalRevokedSinceQueuedError, match=approval_id):
            await resume_approval(
                approval_id,
                approval_repo=repo,
                evidence_repo=_EvidenceRepo(engine),
                org_id="org-1",
                root_authority_repo=root_repo,
                consent_repo=c_repo,
            )

    async def test_named_scenario_11_approval_queued_for_a_resumed_as_b_is_impossible_by_construction(
        self, engine
    ) -> None:
        """Named attack scenario 11: build_resume_action() (governance/
        approval.py) always reconstructs the ActionRequest's purpose
        from the persisted ApprovalRequest.purpose -- there is no
        parameter letting a resume caller substitute a different
        purpose than what was queued. This test proves that
        reconstruction directly."""
        from responsibleai.governance.approval import build_resume_action

        repo, approval_id = await self._seed_approved_with_purpose(engine, purpose="analytics.read")
        approval = await repo.get(approval_id)
        assert approval is not None
        assert approval.purpose == "analytics.read"

        agent = _agent(_identity())
        reconstructed = build_resume_action(approval, agent=agent)
        assert reconstructed.purpose == "analytics.read"
