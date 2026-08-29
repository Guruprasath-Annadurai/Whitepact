# Phase 2 — Execution Boundary Architecture Decision

**Directive**: WHITEPACT — FULL ENTERPRISE PRODUCTION + PUBLIC LAUNCH CLOSURE MASTER DIRECTIVE, Phase 2 ("Make Heart a True Execution Security Boundary").

**Decision**: **Option B, partial — extend the existing structural `ExecutionAuthorization` object (Phase 3 of this same directive) without adding cryptographic signing.** Option A (separate execution-authority service) and full Option C (separate service + signed capability) are explicitly **rejected** for this codebase, with reasoning below. This is a design decision, not a default — it overrides nothing established without justification, and the justification is grounded in this codebase's own prior, already-sound reasoning, not invented for this document.

---

## What the directive's three options actually buy, evaluated against THIS codebase's real threat model

The one open finding Phase 2 exists to close is `ENFORCEMENT_PATH_MATRIX.md`'s Path 8: a direct in-process Python import of `mcp.tools._dispatch_tool_unchecked()`. Every network-reachable path is already closed (Phase E0-E6, prior session). The realistic attacker for the *remaining* gap is: someone with source/deploy access to this codebase, or a supply-chain-compromised dependency loaded into the same running process.

### Option A — separate execution-authority service

Would mean standing up a second process, an authenticated IPC/RPC layer between the application and it, and operating, monitoring, and securing a new network-facing (or at least new-process) surface — for a single-org, single-deployable-unit platform that has no other reason to be a distributed system today.

**Does it actually close the remaining gap?** No, not fully. An attacker with arbitrary code execution inside the *calling* process (the actual precondition for reaching `_dispatch_tool_unchecked()` directly today) can, with equal ease, forge a request to the new authority service, replay a legitimate one, or — if the authority service's own client library is loaded in the same process, which it would have to be to call it — simply monkeypatch that client to always report ALLOW. Moving the decision to a second process changes *where* the check happens; it does not change the fact that the caller asking for the check is the same untrusted code that could bypass any check.

**Verdict**: real distributed-systems complexity (deployment, operations, another attack surface, another thing to keep available) for a security property it does not actually deliver against this specific residual threat. This is exactly the "unnecessary distributed complexity" the directive itself warns against choosing.

### Option B — capability-token architecture (signed)

Heart produces a signed, short-lived capability; the executor refuses to run without a valid signature.

**Does it close the remaining gap?** Also no, for the same reason `governance/execution.py`'s own module docstring already argues, correctly, and predates this directive: *"an attacker able to forge an in-process Python object already has arbitrary code execution in this process, at which point HMAC verification protects nothing."* If the signing key lives in the same process (it would have to, for `authorize_execution()` to use it), an attacker with the arbitrary-code-execution precondition this bypass requires can read that key from process memory as easily as they can call `_dispatch_tool_unchecked()` directly. Signing an object that never crosses a trust boundary adds real implementation complexity (key management, clock-skew handling, verification code, more tests) without removing the actual vulnerability.

**Where signing WOULD matter**: the moment a *future* executor lives in a genuinely separate process or host — the v3 spec's own already-named `MCPExecutor`/`HTTPExecutor` for proxying to *external* systems, not this platform's own 27 tools. That is a real, different, not-yet-built feature. This document does not build it preemptively.

### Option C — combined

Inherits both options' costs; delivers no more security against the residual threat than Option B alone for the same reason.

---

## What IS chosen, and why it's still real, structural work

**Extend `ExecutionAuthorization`'s fields** (this directive's own Phase 3 list: consent reference, policy version, Heart legitimacy-verdict digest, revocation epoch, purpose, execution ID — beyond the `action_digest`/`organization_id`/`decision`/`target_fingerprint` it already carries) **without adding a signature**. This is worth doing on its own merits, independent of the signing question:

- **Better mutation/tamper detection** — today's `action_digest` binds the action's shape; it does not bind *which* consent, *which* policy version, or *which* Heart verdict authorized it. A future audit or a resume-flow bug could silently authorize execution against a decision made under a different policy version than the one now in effect. Binding these fields into the digest makes that class of bug structurally detectable, with no cryptography required — this is the same "structural, not signed" reasoning `execution.py` already uses for the fields it has today, just extended to cover more of what actually authorized the action.
- **Real regression-test value**: mutation/replay/mismatch tests (this directive's own Phase 3 requirement) become meaningful once there's more to mutate and check against.
- **Groundwork, not premature building**: if a future phase genuinely needs a cross-process executor, the capability object already carries every field a signature would need to cover — signing becomes an additive change to an existing shape, not a redesign.

## Enforcement-path proof (re-confirmed, not re-invented)

Every item Phase 2 lists as a requirement was already closed in this branch's prior commits, independently of this decision:

- No public unchecked execution function — `_dispatch_tool_unchecked()`, E5.
- No network route bypass — `ENFORCEMENT_PATH_MATRIX.md`, every hosted transport converges on `InternalToolExecutor`.
- No stdio bypass — E2, `enterprise_mode=true` blocks stdio entirely.
- No demo mode bypass — E4, startup refuses `enterprise_mode=true` + demo flag together.
- No approval-resume bypass — E6, `resume_approval()` re-checks Heart at execution time.
- No alternate transport bypass — Streamable HTTP and legacy SSE share one `_call_tool()`.
- No legacy configuration enabling ungoverned execution — E3 (corrected: no such path existed; the real issue was the demo flag, closed above).

The one item this document does not claim closed: **a direct in-process Python import remains possible for a caller who already has arbitrary code execution in the process** — named honestly, matching this codebase's own established discipline, not papered over by this decision.

## Phase 2 verdict

**READY TO ADVANCE**, with an explicit accepted-risk carve-out: the in-process bypass is a structural property of running untrusted-or-compromised code in the same process as the enforcement logic, and no architecture short of literally separating that code (Option A, rejected above as not actually solving it either, for THIS specific threat) removes it. Phase 3 (extend `ExecutionAuthorization`'s fields) is real, valuable, structural follow-through from this decision — proceeding to it next.
