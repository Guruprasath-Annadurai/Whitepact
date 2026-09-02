# The Known Structural Bypass — Precise Statement (Stage 4)

This document exists because the governing security-freeze directive
explicitly requires this exact bypass to be named precisely, once, in its
own document — not softened, not overclaimed, and not "fixed" with a
cosmetic wrapper. It does not propose a fix. A fix requires a real
architecture decision (process boundary, IPC mechanism, credential
passing, replay/revocation semantics across that boundary) that this
document deliberately does not make — see the placeholder note at the end
for where that work belongs (Stage 10, not this stage).

## The exact bypass

`responsibleai.mcp.tools._dispatch_tool_unchecked()` (formerly
`dispatch_tool()`, renamed under Phase E5) is the raw, ungoverned
implementation every governed execution path in this codebase eventually
calls through — via `InternalToolExecutor`, `UpstreamMCPExecutor`, or the
stdio fallback. It takes no caller-identity parameter and has no
structural means to distinguish a governed caller from an ungoverned one.

**Any Python code running inside the same OS process as this function —
with ordinary `import` access to the `responsibleai` package — can call it
directly, bypassing every governance layer this codebase builds:**
policy evaluation, Heart legitimacy resolution, purpose binding, consent
checks, `ExecutionAuthorization` issuance, evidence recording, and audit
logging all sit *above* `_dispatch_tool_unchecked()` in the call graph,
never inside it or below it.

## Two categories that must not be conflated

### Network-reachable execution

Every path in `docs/heart-production-closure/ENFORCEMENT_PATH_MATRIX.md`
except Path 8 (this bypass) and Path 9 (an unrelated CLI) is reached over
a network transport (MCP stdio counts as "network-reachable" only in the
loose sense that it's a process boundary a local client crosses — see
that document's own Path 1 entry for its specific, narrower guarantees).
For these paths, under `enterprise_mode=true` and the other flags that
matrix documents per-path, governance is expected to run and has been
tested to run, with independently reproduced test evidence
(`FROZEN_REVIEW_VERIFICATION.md`). **This is a claim about what an
external caller — anyone who does not already have code execution inside
the WhitePact process — can reach.** It is bounded by the matrix's own
per-path caveats (several paths bypass governance under specific,
documented flag combinations that are not this structural gap).

### In-process trusted-code execution

`_dispatch_tool_unchecked()` sits inside the *same trust domain* as the
rest of the running process. Anyone who can get their own code to execute
inside that process — a compromised dependency, a malicious plugin, a
careless internal script, an operator with shell access to the running
service, a supply-chain-compromised package loaded at import time — can
call it directly and skip governance entirely. **This is not a network
attack surface.** It requires code execution inside the process already,
which is a different, and in most deployment models more severe,
precondition than "an unauthenticated network request." But once that
precondition holds, no code in this repository stops the call.

## What this is not

- **Not a missed wiring gap.** Every governed path's own code correctly
  calls through the same executor layer; there is no forgotten
  `if enterprise_mode` check anyone simply failed to add on a legitimate
  path.
- **Not closeable by renaming, wrapping, or re-exporting.** The Phase E5
  rename (`dispatch_tool` → `_dispatch_tool_unchecked`) and its drift-guard
  test (`tests/test_dispatch_tool_unchecked_call_sites.py`) bound
  *accidental* new call sites and re-exports — they do not, and cannot,
  stop a deliberate direct import by code already running in the process.
  A leading underscore is a Python naming convention, not an access
  control mechanism; `importlib` does not consult it.
- **Not closeable by a runtime check inside the function itself.** Any
  check added inside `_dispatch_tool_unchecked()` (e.g. "reject unless a
  valid `ExecutionAuthorization` is passed") only holds if every caller is
  *required* to construct one truthfully — and an in-process caller with
  the same code-execution privilege as the function itself can construct,
  forge, or simply skip whatever object such a check demands, because
  there is no cryptographic or OS-level boundary between "the code that
  checks" and "the code being checked." This is a general property of
  same-process trust, not specific to this codebase.

## What would actually close it

Only a real **process boundary** — where the executor and the governance
decision-maker run in genuinely separate address spaces, communicating
over a channel the executor cannot forge its way around (a Unix-domain
socket with peer-credential checks, a separate OS process reached only via
a narrow IPC surface, a network service reached only with a
structurally-verifiable, short-lived, cryptographically bound execution
authorization) — would remove the in-process caller's ability to invoke
the raw function at all, because there would no longer be a raw function
in the same process to invoke. This is real architectural work: it
changes deployment topology, adds a new failure mode (the executor
process being unreachable), and requires solving credential-passing,
authorization-serialization, and revocation-propagation across the new
boundary. **That design work is explicitly out of scope for this
document** and is not started here — it belongs to Stage 10 of the
governing directive (`docs/architecture/EXECUTION_PROCESS_BOUNDARY.md`,
not yet written), which the directive itself says must not be implemented
before a design comparing multiple real options is written and approved.

## Required framing for any public or customer-facing claim

Per the governing directive's own rule (Stage 12, "public claim audit"),
any statement about this system's execution guarantees must distinguish
these two categories explicitly. It is **accurate** to say: "every
network-reachable execution path requires Heart legitimacy when
enterprise mode is enabled, as independently verified by
[evidence]." It is **not accurate** to say, and must never be said: "all
execution paths are impossible to bypass," "execution is fully isolated,"
or any claim of complete process isolation — none of those are true today,
and this document exists specifically so no later document, PR
description, or public page can plausibly claim otherwise "by omission."

## Status

**OPEN. Not closed. Not being closed by this document or this stage.**
Recorded, precisely, as the one honestly-disclosed structural gap this
entire branch's Heart/enforcement work still carries.
