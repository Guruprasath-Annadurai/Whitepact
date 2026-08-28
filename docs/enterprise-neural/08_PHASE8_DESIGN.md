# Phase 8 — LLM + Agent Security Boundary: Design

STATUS: Design/audit. No runtime code changed by this document.

## 0. Ground truth — most of this phase's requirements already hold

Per the master directive's own rule 63 ("inspect before implementing...
do not rebuild systems merely to satisfy this prompt"), this phase
starts with an audit, not a rebuild. Reading `mcp/governance_integration.py`
and `governance/execution.py` (both already reviewed in the original
Phase 0 repository audit) confirms most of directive §8's requirements
are **already true**, structurally, not by convention:

| Directive §8 requirement | Status in this codebase |
|---|---|
| LLM must never issue/sign authority | Already true — `AuthorityGrant`/`AuthorityEnvelope` are constructed only inside `governance/gateway.py`/`governance/authority_grant.py`, never from LLM-controlled input. No code path takes raw LLM output and treats it as an authority object. |
| LLM must never create execution permits | Already true — `ExecutionAuthorization` is constructed only by `mcp/governance_integration.py` after a gateway decision, never by tool-call arguments. `InternalToolExecutor.execute()` structurally requires a matching, unexpired, single-use authorization (`governance/execution.py`) — verified by `tests/test_executor_bypass_invariant.py` already, per the original repo audit. |
| Uncertainty/failure must never become implicit ALLOW | Already true — `EvidenceRepository.record()` failures fail closed (block the call), documented in `THREAT_MODEL.md` §3, verified by `TestEvidenceWriteFailsClosed`. |
| Action mutation must invalidate authorization | Already true for the non-neural path (`ExecutionAuthorization.action_digest`, `AuthorizationTargetDriftError`) — and now also true for the neural path (Phase 7, this session). |
| Treat every LLM/tool response as untrusted input | Partially true — `ActionRequest`'s `arguments` are typed but not schema-validated against a tool's declared schema before reaching governance (see Gap 2 below). |

## 1. Real gaps found (not assumed, read from the code and its own docstrings)

1. **Self-hosted stdio transport is ungoverned** — `mcp/governance_integration.py`'s
   own docstring states this plainly: "the self-hosted stdio transport...
   has no organizational identity to build an AuthorityContext/Policy
   against and is therefore never governed by this path regardless of
   the setting." This is a known, pre-existing, self-documented gap —
   not discovered by this phase, but worth restating in this initiative's
   own tracking rather than silently treating it as covered. **Out of
   scope for this phase**: closing it requires adding organizational
   identity to the stdio transport, a materially larger architectural
   change than this phase should attempt (the same "don't silently wire
   into a live path" discipline this whole initiative has followed).
2. **No invariant connects the neural track (Phases 4-7) to the LLM
   boundary** — nothing currently prevents an LLM/agent-controlled code
   path from calling `mint_neural_intent_attestation()` directly (it's
   a plain importable function). In practice this requires the caller
   to already hold a `dek`/`KeyId` from `governance/crypto`'s
   `KeyProvider` — which an LLM has no route to obtain (no code path
   exposes key material to LLM-controlled input) — but this is true
   *incidentally*, by the absence of a wiring path, not because of an
   explicit, tested invariant. This phase closes that gap: add an
   explicit test suite proving the specific directive-named properties
   hold against the real, existing gateway/execution/neural code.
3. **No schema validation of LLM-supplied tool arguments before they
   reach governance** — `ActionRequest.arguments` is `dict[str, Any]`,
   validated by nothing before `WhitePactRuntimeGateway.evaluate()`
   sees it. This is a real gap but re-architecting tool-argument schema
   validation is a larger, separate initiative (would touch every
   existing tool definition in `mcp/tools.py`) — flagged here, not
   silently fixed by a narrow patch that wouldn't actually close it.

## 2. What this phase delivers

Given the audit above, the correct, non-inflated scope for Phase 8 is:
an **invariant test suite** proving the properties the directive names
hold against the real, already-existing code (not fixtures, not mocks)
— the same kind of "prove it, don't assume it" discipline this session
applied throughout. Concretely:

- LLM-controlled `ActionRequest` data alone can never construct a valid
  `ExecutionAuthorization` (must come from `authorize_execution()`,
  itself gated on a governance decision).
- An `ExecutionAuthorization` whose `action_digest` doesn't match the
  action about to execute is refused (`AuthorizationActionMismatchError`).
- A `NeuralIntentAttestation` cannot be verified without the exact
  signing key — an attacker with LLM-level access (no key material)
  cannot forge one (reuses Phase 7's own property tests' evidence,
  cited not re-derived).
- `mint_neural_intent_attestation`/`verify_neural_intent_attestation`
  have no code path reachable from unauthenticated/LLM-originated input
  in this codebase today (a structural code-search assertion, not a
  runtime test — documented as such).

## 3. What this phase does not do

- Does not add organizational identity to the stdio transport (Gap 1).
- Does not add tool-argument schema validation (Gap 3) — a separate,
  larger initiative.
- Does not modify `mcp/governance_integration.py` or
  `governance/execution.py` — this phase proves properties about
  existing code, it doesn't change it (nothing found requires a code
  fix, only evidence).

## 4. Implementation plan

1. `docs/enterprise-neural/08_PHASE8_REPORT.md`'s evidence section
   documents the structural code-search findings for Gap 2/Requirement
   4 above.
2. `tests/test_llm_agent_security_boundary.py`: the invariant test
   suite from Sec 2, exercising real `governance/execution.py` and
   `governance/neural/attestation.py` code.
3. Phase Report.
