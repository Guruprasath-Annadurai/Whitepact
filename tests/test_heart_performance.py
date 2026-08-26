"""Heart Phase H16 — Performance.

First-ever latency/throughput measurements for the Heart's hot paths:
`sovereignty_kernel.evaluate()` (the orchestration entry point, H13)
and the two operations Phase H15's own gauntlet work flagged as
depth/size-sensitive (`validate_root_chain()`'s chain walk, H3;
`check_non_delegable_authority()`'s O(action_types × registry) scan,
H7). See `docs/heart/HEART_PERFORMANCE.md` for the full baseline
report and methodology notes.

**Generous, non-tuned bounds, matching H9's own established pattern**
(`tests/test_concurrency.py::TestDelegationRevokeBranchLatency`): these
assertions exist to catch a real algorithmic regression (e.g.
accidentally reintroducing O(n²) behavior), not to enforce a tuned
SLA. Bounds are set at roughly 10-20x the measured baseline on the
machine these tests were first written on, to avoid flaking under
normal CI variance while still being tight enough to fail if
performance genuinely degrades by an order of magnitude.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from responsibleai.governance import sovereignty_kernel as sk
from responsibleai.governance.consent_proof import ConsentMethod, build_consent_proof
from responsibleai.governance.delegation import DelegationRecord
from responsibleai.governance.intent import IntentContract
from responsibleai.governance.non_delegable_authority import check_non_delegable_authority
from responsibleai.governance.purpose_binding import build_purpose_binding
from responsibleai.governance.root_authority import (
    RootType,
    build_root_authority_record,
    validate_root_chain,
)


class TestEvaluateLatency:
    def test_full_chain_evaluate_completes_promptly_at_scale(self) -> None:
        human = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
        proof = build_consent_proof(
            "u1", human.root_id, "agent1", "scope", "purpose-x", ConsentMethod.EXPLICIT_UI_ACTION
        )
        intent = IntentContract(organization_id="org1", agent_id="agent1", goal="g")
        binding = build_purpose_binding("purpose-x", intent.contract_id, proof.consent_id)
        delegation = DelegationRecord(
            delegation_id="d1",
            org_id="org1",
            from_identity_id=None,
            to_identity_id="agent1",
            granted_action_types=frozenset({"payment.execute"}),
            constraints={},
            require_approval_for=frozenset(),
            purpose="purpose-x",
            granted_by="u1",
            granted_at=datetime.now(UTC),
        )

        n = 1000
        started = time.perf_counter()
        for _ in range(n):
            sk.evaluate(
                "org1",
                "agent1",
                root=human,
                consent=proof,
                intent=intent,
                purpose_binding=binding,
                delegation=delegation,
            )
        elapsed = time.perf_counter() - started

        # Baseline measured ~17us/call on the machine this test was
        # first written on -- 1000 calls in well under a second.
        # Bound is generous (2s for 1000 calls = 2ms/call, ~100x
        # baseline) to absorb CI variance while still catching a real
        # regression.
        assert elapsed < 2.0, f"1000 full-chain evaluate() calls took {elapsed:.3f}s"

    def test_empty_input_evaluate_completes_promptly_at_scale(self) -> None:
        n = 1000
        started = time.perf_counter()
        for _ in range(n):
            sk.evaluate("org1", "agent1")
        elapsed = time.perf_counter() - started
        assert elapsed < 1.0, f"1000 empty-input evaluate() calls took {elapsed:.3f}s"


class TestRootChainWalkLatency:
    def test_deep_chain_validate_root_chain_completes_promptly(self) -> None:
        prev = build_root_authority_record("root0", RootType.ORGANIZATION, "issuer", "saml")
        store = {prev.root_id: prev}
        for i in range(32):
            nxt = build_root_authority_record(
                f"sp{i}", RootType.SERVICE_PRINCIPAL, "issuer", "jwt", authority_source=prev.root_id
            )
            store[nxt.root_id] = nxt
            prev = nxt

        n = 500
        started = time.perf_counter()
        for _ in range(n):
            validate_root_chain(prev, lambda rid: store.get(rid))
        elapsed = time.perf_counter() - started

        # Baseline ~17us/call for a full 32-hop chain walk.
        assert elapsed < 1.0, (
            f"500 deep-chain (32-hop) validate_root_chain() calls took {elapsed:.3f}s"
        )


class TestNonDelegableAuthorityScaling:
    """check_non_delegable_authority() is O(action_types x registry
    size) in the worst case (no match found, every action type
    checked against every pattern). This is a real, documented scaling
    characteristic, not a bug -- see HEART_PERFORMANCE.md for the full
    measurement and discussion of when it could matter."""

    def test_large_action_type_set_with_no_match_completes_promptly(self) -> None:
        action_types = frozenset({f"action.type.{i}" for i in range(1000)})
        n = 50
        started = time.perf_counter()
        for _ in range(n):
            result = check_non_delegable_authority(action_types)
        elapsed = time.perf_counter() - started

        assert result is None
        # Baseline ~4.3ms/call for 1000 non-matching action types --
        # generous bound (10s for 50 calls = 200ms/call, ~45x
        # baseline) since this is the known-slower path.
        assert elapsed < 10.0, f"50 calls with 1000-entry action_types took {elapsed:.3f}s"

    def test_early_match_is_fast_regardless_of_set_size(self) -> None:
        """check_non_delegable_authority() checks action_types in
        sorted order; "heart.veto.override" sorts before any
        "zzz.action.N" entry, so a match is found on (roughly) the
        first sorted element rather than requiring a full scan of a
        1000-entry set."""
        action_types = frozenset({"heart.veto.override"} | {f"zzz.action.{i}" for i in range(1000)})
        started = time.perf_counter()
        result = check_non_delegable_authority(action_types)
        elapsed = time.perf_counter() - started
        assert result is not None
        assert elapsed < 0.1
