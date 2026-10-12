# Agentic threat register (OWASP Top 10 for Agentic Applications 2026 classes + the order's list)

For each threat: the boundary an attacker tries to cross, whether WhitePact claims to defend it, what was
actually run, and the status. **A threat WhitePact does not mediate is "OUT OF SCOPE", not "prevented".**
Vocabulary: ENGINEERING PASS (implemented and tested, independent review pending), NOT TESTED, OUT OF SCOPE,
PARTIAL. No row here is independently verified.

| # | Threat | Boundary the attacker tries to cross | In scope? | What was run | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | Agent hijacking / prompt injection | Make injected text change a governance decision | Yes: decisions must not depend on content | `test_agentic_adversarial.py`: 10 injection payloads × 4 decisions in arguments, results, nested data, purpose and target names; decision and reason codes identical to the clean baseline | ENGINEERING PASS |
| 2 | Excessive agency | Perform an action the agent holds no authority for | Yes | `test_executor_bypass_invariant.py`, `test_v1_exactly_one_effect.py`, `test_approval_adversarial.py` | ENGINEERING PASS |
| 3 | Identity and privilege abuse | Forged, expired, revoked, wrong-tenant, read-only credentials; cross-tenant approval and evidence | Yes | `test_transport_credential_negatives.py` (7), `test_mcp_http_credential_negatives.py` (4), `test_step_up_forged_proofs_http.py` (16) | ENGINEERING PASS |
| 4 | Containment escape | Leave the container, reach the network, replace the runner | Yes (Linux) | `test_runtime_isolation_*`, `test_runner_immutability.py`, `test_isolation_real_tool_e2e.py` on a Linux 6.12 kernel (root and uid 1001); macOS records QUALIFICATION_SKIP | ENGINEERING PASS on Linux; host-side fixture exception **not independently reviewed** |
| 5 | Memory poisoning | Plant instructions in agent memory that later authorize actions | Partial: memory-authority checks exist for writes/reads through governance | `test_mcp_governance_dispatch.py::TestMemoryAuthority` | PARTIAL |
| 6 | Multi-agent cascading failure | One compromised agent widens authority through delegation | Yes | `validate_attenuation` tests in `test_agentic_adversarial.py` (widened actions, higher limit, lifted denial refused); cascading `revoke_branch`; resolver cycle and depth limits (`test_delegation_graph.py`) | ENGINEERING PASS |
| 7 | Supply-chain compromise | Malicious dependency, tool or upstream server change | Partial | pip-audit/npm audit/dependency-review/gitleaks in CI; upstream fingerprint-drift refusal; images pinned by digest | PARTIAL; no SBOM or signed provenance verified here |
| 8 | Unexpected code execution | A tool runs code outside its sandbox | Yes (through isolation) | as #4 | ENGINEERING PASS on Linux |
| 9 | Data exfiltration | Send data out through an allowed channel | Partial: egress is blocked inside the container; allowed destinations are not content-inspected | nftables namespace test (local) | PARTIAL |
| 10 | Hallucinated or falsely reported actions | The agent claims an effect that did not happen, or hides one that did | Yes (outcome recording) | UNKNOWN outcome with mandatory reconciliation, no automatic retry (`test_v1_exactly_one_effect.py`) | ENGINEERING PASS |
| 11 | AI-assisted cyber abuse | Using the agent to attack third parties | OUT OF SCOPE (content intent is not judged here) | none | OUT OF SCOPE |
| 12 | Deepfake-enabled authorization fraud | Fake a human approver | Partial: approvers are authenticated humans with TOTP step-up; no liveness or biometric check | `test_step_up_forged_proofs_http.py` | PARTIAL. The deepfake detector is experimental and NOT a control |
| 13 | Human-agent manipulation | Persuade an approver | OUT OF SCOPE as a technical control; approval screens show the exact action and arguments | none | OUT OF SCOPE |
| 14 | Untraceable actions | Act without evidence | Yes | evidence on every decision; 60 concurrent decisions give one unbroken hash chain; restore drill keeps the chain; policy edits attributed | ENGINEERING PASS; no external immutability claimed |
| 15 | Runaway loops | Unbounded repeated actions | Partial: quarantine after repeated violations, autonomy budgets, plan limits | `TestQuarantineAfterRepeatedViolations`, `TestAutonomyBudget`; HTTP run showed no unauthorized effects at 1,000 connections | PARTIAL; the 30/min route limit (REC-28) caps legitimate use |
| 16 | Guardrail bypass | Evade content scanning | Heuristic only | red-team and guardrail unit tests | EXPERIMENTAL; heuristic, not a boundary |
| 17 | Stale authorization | Use authority after it was withdrawn | Yes for new admissions | revocation after approval (`409 Current security state denied resume`), policy change after approval, revoked key mid-session | ENGINEERING PASS; **an already-running tool is not cancelled** (stated in the enforcement matrix) |
| 18 | Transitive capability escalation | Gain capability through a chain | Yes | as #6 | ENGINEERING PASS |
| 19 | Rogue / specification-gaming behaviour | The agent satisfies the letter of a rule | OUT OF SCOPE except through policy review | none | OUT OF SCOPE |
| 20 | Loss of independence of the enforcement boundary | The agent influences its own authorizer | Yes | decisions made server-side from identity, authority, policy; in-process unisolated execution refused in production under every environment spelling; one host-side fixture exception, disclosed | ENGINEERING PASS; REC-12 review pending |

## What this does not show

No adversarial run was made against a deployed system, a third-party model, or real customer data. The injection
corpus is ten harmless strings, not a fuzzer. Passing it shows that the decision path does not read content; it does
not show that no other path does.
