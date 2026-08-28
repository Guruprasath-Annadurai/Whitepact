"""Tests for Enterprise Neural Phase 8 (LLM + Agent Security Boundary).

Per `docs/enterprise-neural/08_PHASE8_DESIGN.md`: most of the master
directive's §8 requirements ("LLM must never issue/sign authority or
create execution permits") already hold structurally in this codebase,
established by prior initiatives (Heart, Production Integration,
Authority Everywhere). This phase's job is to *prove* those properties
against the real, existing code — not fixtures, not mocks — rather than
assume the docstrings that state them are still accurate.

Two kinds of evidence:
1. Structural regression guards: a source-text scan confirming a
   security-critical object (`ExecutionAuthorization`, `AuthorityGrant`)
   has exactly one construction site in the codebase — the gated
   factory function, never a raw call reachable from LLM/tool-dispatch
   code. Heuristic (text-based, not a full AST/import-graph analysis),
   documented as such — the same honesty this session applied to
   `scripts/rotate_field_encryption_key.py`'s own heuristic legacy-
   ciphertext check. A false positive (a legitimate new call site this
   scan doesn't recognize) fails loud and gets reviewed; a false
   negative (missing a real bypass) is the risk this guard exists to
   shrink, not eliminate.
2. Runtime tests: `authorize_execution()` refuses to produce an
   authorization for anything other than an ALLOW/ALLOW_WITH_REDACTION
   `DecisionResult` — which itself can only come from
   `WhitePactRuntimeGateway.evaluate()`, never from LLM-controlled
   `ActionRequest` data alone.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from responsibleai.governance.execution import (
    DecisionNotExecutableError,
    authorize_execution,
)
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    DecisionResult,
    GovernanceDecision,
    IdentityContext,
)

_SRC_ROOT = Path(__file__).parent.parent / "src" / "responsibleai"


def _construction_call_sites(class_name: str, defining_file: Path) -> list[Path]:
    """Every `.py` file under `_SRC_ROOT` containing a `ClassName(` call,
    other than *defining_file* itself. Heuristic text scan — see module
    docstring."""
    pattern = re.compile(rf"\b{re.escape(class_name)}\(")
    hits = []
    for path in _SRC_ROOT.rglob("*.py"):
        if path == defining_file:
            continue
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            hits.append(path)
    return hits


class TestExecutionAuthorizationSingleConstructionSite:
    def test_execution_authorization_is_never_constructed_outside_governance_execution(
        self,
    ) -> None:
        """`ExecutionAuthorization` per its own module docstring:
        "deliberately not cryptographically signed... as long as it
        never crosses a trust boundary" -- that safety property depends
        entirely on it having exactly one, gated construction site
        (`authorize_execution()`). If a second call site appears
        anywhere else in the codebase (e.g. a new module hand-rolling
        one from LLM/tool-call-controlled data), that safety property
        is silently broken -- this guard catches it."""
        defining_file = _SRC_ROOT / "governance" / "execution.py"
        hits = _construction_call_sites("ExecutionAuthorization", defining_file)
        assert hits == [], (
            f"ExecutionAuthorization constructed outside governance/execution.py: {hits} "
            "-- authorize_execution() must be the only gated construction site."
        )


class TestAuthorityGrantSingleConstructionSite:
    def test_authority_grant_is_never_constructed_outside_its_own_module(self) -> None:
        """`AuthorityGrant` must only ever be constructed via
        `build_authority_grant()` (`governance/authority_grant.py`) --
        the same "LLM must never issue/sign authority" property this
        whole initiative's Heart work exists to guarantee."""
        defining_file = _SRC_ROOT / "governance" / "authority_grant.py"
        hits = _construction_call_sites("AuthorityGrant", defining_file)
        assert hits == [], (
            f"AuthorityGrant constructed outside governance/authority_grant.py: {hits} "
            "-- build_authority_grant() must be the only construction site."
        )


class TestNeuralIntentAttestationMintingIsNotWiredToAnyLlmReachablePath:
    def test_mint_neural_intent_attestation_has_no_call_site_outside_its_own_module(
        self,
    ) -> None:
        """Per Phase 7's own report: nothing in the shipped codebase
        calls `mint_neural_intent_attestation()` yet. This guard makes
        that an enforced, regression-tested property rather than a
        point-in-time observation that could silently go stale as later
        phases add code."""
        defining_file = _SRC_ROOT / "governance" / "neural" / "attestation.py"
        hits = _construction_call_sites("mint_neural_intent_attestation", defining_file)
        # The __init__.py re-export is expected and safe (it doesn't
        # call the function, only imports the name) -- excluded
        # explicitly since it's not a call site.
        hits = [h for h in hits if h.name != "__init__.py"]
        assert hits == [], (
            f"mint_neural_intent_attestation() called from: {hits} -- if this is "
            "intentional new wiring, this test should be updated deliberately, not "
            "silently left broken."
        )


class TestAuthorizeExecutionRequiresARealGatewayDecision:
    """The runtime half of the invariant: even granting an attacker full
    control over `ActionRequest` construction, they cannot produce an
    `ExecutionAuthorization` without a `DecisionResult` whose `decision`
    field is ALLOW/ALLOW_WITH_REDACTION -- which only
    `WhitePactRuntimeGateway.evaluate()` produces, not LLM-controlled
    input."""

    def _action(self) -> ActionRequest:
        return ActionRequest(
            agent=AgentContext(
                identity=IdentityContext(identity_id="agent1", kind="agent"),
                organization_id="org1",
            ),
            action_type="rai_scan",
            target="some-target",
            arguments={"attacker_controlled": "value"},
        )

    @pytest.mark.parametrize(
        "decision_value",
        [
            GovernanceDecision.DENY,
            GovernanceDecision.QUARANTINE,
            GovernanceDecision.REQUIRE_APPROVAL,
        ],
    )
    def test_non_executable_decisions_never_produce_an_authorization(
        self, decision_value: GovernanceDecision
    ) -> None:
        decision = DecisionResult(decision=decision_value, action_id="a1")
        with pytest.raises(DecisionNotExecutableError):
            authorize_execution(decision, self._action())

    def test_an_attacker_supplied_action_alone_cannot_forge_an_allow_decision(self) -> None:
        """`DecisionResult` is a typed object with a `GovernanceDecision`
        enum field -- there is no string/dict-shaped "decision" an
        attacker could smuggle through `ActionRequest.arguments` that
        `authorize_execution` would ever interpret as ALLOW. Arguments
        are opaque `dict[str, Any]` payload, never inspected for a
        decision value."""
        action = ActionRequest(
            agent=AgentContext(
                identity=IdentityContext(identity_id="agent1", kind="agent"),
                organization_id="org1",
            ),
            action_type="rai_scan",
            target="t",
            arguments={"decision": "ALLOW", "reason_code": "trust me"},
        )
        # authorize_execution takes the decision as a separate,
        # explicit parameter -- it never derives one from `action`.
        # Calling it with a real DENY decision proves the arguments
        # dict has no bearing on the outcome.
        decision = DecisionResult(decision=GovernanceDecision.DENY, action_id="a1")
        with pytest.raises(DecisionNotExecutableError):
            authorize_execution(decision, action)
