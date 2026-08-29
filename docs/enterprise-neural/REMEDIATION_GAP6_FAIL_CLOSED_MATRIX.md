# Security Remediation Gap 6 — Fail-Closed Coverage Expansion

## Reproduction

Independently re-verified: `tests/test_resilience_fail_closed_matrix.py`
(Enterprise Neural Phase 14) tests exactly one pattern —
`TestPreEvaluateDependencyCrashesFailClosed`, parametrized over the six
repository lookups `apply_governance()` calls before
`gateway.evaluate()` — plus DB (loosely, via those same six methods).
Against the remediation directive's named list of ~17 failure
categories, the rest were untested by this exact name. For each, the
question was: is there a real code gap, or just a missing test for
already-correct behavior?

## Disposition of every named category

| Category | Disposition |
|---|---|
| DB (repo methods) | Already tested (Phase 14) |
| Policy-engine (repo lookup) | Already tested (Phase 14) |
| **Policy-engine (`Policy.evaluate()` itself)** | **New test this phase** — distinct code path, previously untested |
| **Individual tool crash mid-execution** | **New test this phase** |
| **Network-timeout (upstream MCP)** | **New test this phase** |
| **Key-rotation-mid-request** | **New test this phase** |
| Audit-store, pre-execution write failure | Already tested (`test_mcp_governance_dispatch.py::TestEvidenceWriteFailsClosed`) |
| Audit-store, post-execution outcome write failure | Already correct **and intentionally fail-open** — the tool already ran; nothing left to block (`governance_integration.py`'s own docstring, "Outcome Observation... fail-open, unlike evidence") |
| Cache (Redis, rate limiting) | Out of scope — a rate-limiter failure affects throttling, not an authorization decision; not a security-critical fail-closed cell |
| Clock / clock skew | No dedicated abstraction exists; only use is a plain `datetime.now(UTC)` comparison (`execution.py`'s `ExecutionAuthorization.is_expired`) with nothing meaningfully "unavailable" to test |
| KMS unavailable mid-request | **N/A by construction** — per-request key material comes from an in-process cache (`db/encryption.py`'s `_active_field_encryption_key`), set once at startup; a live request never calls a `KeyProvider` again |
| Heart / Brain / Citadel / LLM-decision-path / neural-vault / decoder / BCI-disconnect | **N/A today** — none of these is wired into `gateway.py`/`governance_integration.py`'s live decision path yet (confirmed: zero references to `heart_veto`/`sovereignty_kernel` in either file). "Unavailable" doesn't apply to something never called. Correctly deferred to Gap 3's remaining wiring phases (Phase 5 Authority Resolver, Phase 6 live wiring) — force-testing these now would either fabricate a call path that doesn't exist or test nothing real |
| Signature-error (`audit_anchor.verify_anchor_from_provider()` returning invalid) | **Purely advisory today** — called only from `tests/test_audit_anchor.py`; no application code path consults it before an ALLOW/DENY decision. Flagged explicitly here so nobody assumes Gap 5's anchor is protecting live traffic yet — it verifies external evidence integrity offline/on-demand, not gating requests |

## What this phase adds

Four new test classes in `tests/test_resilience_fail_closed_matrix.py`:

- **`TestPolicyEngineCrashFailsClosed`** — `Policy.evaluate()` itself
  raising (not its repository lookup) still fails closed. Reachable on
  every governed call: `PolicyRepository.get_policy()` always returns
  a real `Policy` instance (empty rules if none configured, never
  `None`), so `policy.evaluate()` genuinely runs regardless of whether
  an org has configured any rules.
- **`TestIndividualToolCrashFailsClosed`** — a tool whose governance
  *decision* was ALLOW but whose implementation crashes during
  execution never returns a fabricated success payload.
  `mcp/governance_integration.py`'s `except Exception: ...ERRORED...;
  raise` around `_executor.execute()` is what already guarantees this.
- **`TestUpstreamNetworkTimeoutFailsClosed`** — a proxied call to a
  registered external MCP server whose connection times out
  propagates the exception; `UpstreamMCPExecutor.execute()` has no
  try/except swallowing it.
- **`TestKeyRotationMidRequestFailsClosed`** — the one category worth
  a closer look (see below): proves a value encrypted under a
  pre-rotation field-encryption key, read after the active key
  changes, raises `DecryptionError` rather than returning wrong or
  corrupted plaintext. `governance/crypto/envelope.py`'s
  `decrypt_envelope()` enforces this (embedded `KeyId` must match the
  expected one); this test proves the enforcement reaches through the
  full `EncryptedString` SQLAlchemy column type, not just the
  lower-level primitive.

All four are **tests for already-correct code**, not code fixes — every
path inspected uses the same unwrapped-exception-propagation or
explicit-try/except-then-block pattern the six originally tested
dependencies already established as correct.

## The one thing worth flagging as a real, unaddressed gap

Key rotation itself has no observed mid-flight coordination mechanism:
`db/encryption.py` caches exactly one `(KeyId, dek)` tuple, set once at
startup via `configure_field_encryption_key()`. A live rotation
(calling that function again with a new key) doesn't invalidate or
re-encrypt anything already written under the old key — it just makes
old ciphertext fail closed on next read (proven above), rather than
transparently readable. This is not a fail-*open* security bug — the
system correctly refuses to guess — but it is a genuine, undocumented
operational gap: an actual rotation needs an explicit
"re-encrypt-then-switch" procedure (the repository already has
`scripts/rotate_field_encryption_key.py` for this), and there is no
test proving that script coordinates correctly with concurrent
in-flight requests. That coordination is real, separate work, not
something this phase's four new tests fix — named honestly here rather
than silently left for someone to discover in production.

## Verification

- 11 tests in `tests/test_resilience_fail_closed_matrix.py` (6
  pre-existing + 5 new), all passing.
- `ruff check` / `ruff format --check` clean.
- `mypy src/responsibleai`: clean, 167 source files (no source code
  changed this phase — only tests and docs).
- Full repository suite: see commit for the exact pass count at time
  of commit, run fresh.
