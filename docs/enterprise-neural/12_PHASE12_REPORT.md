# Phase 12 — Platform + Network + Service Isolation: Report

STATUS: **PASS**. Audit-driven. `THREAT_MODEL.md` already documents
every gap this phase's objective names — the discipline of stating
gaps honestly rather than implying mitigation predates this phase and
is preserved, not reset. One gap was genuinely closeable in-repo
(startup visibility for a disabled default); the rest are correctly
out of scope, named explicitly.

## Objective

Per `docs/enterprise-neural/12_PHASE12_DESIGN.md`: verify the master
directive's Phase 12 ("Platform + Network + Service Isolation")
against `THREAT_MODEL.md`'s already-documented gaps and
`00_PHASE0_AUDIT.md`'s KMS/HSM finding — per directive rule 63, close
only what's genuinely actionable without inventing infrastructure this
phase has no go-ahead to build.

## Current state before phase

`THREAT_MODEL.md` §1 already documented: DNS rebinding protection
defaulting to disabled for the hosted MCP HTTP/SSE transport (real,
verified in `mcp/server.py`'s `_build_transport_security()`); no
application-layer message signing (TLS-only, deployer responsibility);
no per-connection SSE timeout (no config knob exists to check).
`00_PHASE0_AUDIT.md` §4 documented KMS/HSM key management as not
implemented. `governance/crypto/provider.py`'s `KeyProvider` Protocol
(Phase 2) already provides the backend-agnostic seam a future
KMS/HSM-backed implementation would need, without touching any caller.

## Architecture implemented

One small, real addition, not new architecture:

- `mcp/server.py`: `platform_isolation_problems(transport_security_enabled)`
  — a pure function, no I/O, returning a human-readable finding when
  DNS rebinding protection ends up disabled. Mirrors
  `dashboard/config.py`'s existing `multi_replica_problems()` pattern:
  pure, unit-testable in isolation, logged as a non-blocking warning
  at startup (not a hard failure — an empty allowlist with protection
  force-enabled would reject every request, the same reasoning
  `_build_transport_security()`'s own docstring already gives for the
  backward-compatible default). Wired into `_build_http_app()`
  immediately after `_build_transport_security()` is computed.

## Files created

- `tests/test_platform_isolation.py`
- `docs/enterprise-neural/12_PHASE12_DESIGN.md`
- `docs/enterprise-neural/12_PHASE12_REPORT.md` (this file)

## Files modified

- `mcp/server.py` — `platform_isolation_problems()` added; wired into
  `_build_http_app()`.
- `THREAT_MODEL.md` — corrected a stale claim: "no upstream/third-party
  MCP proxy executor exists yet to have the same [bypass-invariant]
  property" is now false, per Phase 11's finding that
  `UpstreamMCPExecutor` has the identical property, independently
  tested.
- `CHANGELOG.md`, `docs/enterprise-neural/PROGRESS_LEDGER.md`.

## Database migrations

None.

## Security properties added

A deployer running the hosted MCP HTTP/SSE transport now gets a
startup-time warning if DNS rebinding protection ends up disabled —
previously silent. Not a new mitigation (the underlying protection
mechanism, `TransportSecuritySettings`, already existed) — this closes
the *visibility* gap, not the underlying one, which remains
deliberately opt-in per `_build_transport_security()`'s own documented
reasoning.

## Privacy properties added

None new.

## Trust boundaries changed

None.

## Threats mitigated

The "deployer unaware their hosted MCP transport has no DNS-rebinding
protection" case now produces a visible startup warning instead of
silence.

## Threats not yet mitigated — named explicitly, not glossed over

1. **No application-layer message signing for the MCP transport.**
   Correctly out of scope: inventing a signing scheme the spec doesn't
   require, with no requested provider/mechanism, would be exactly the
   unrequested rebuild directive rule 63 prohibits. Relies on TLS at
   the reverse proxy, the deployer's stated responsibility.
2. **No per-connection SSE timeout / DoS protection.** Correctly out
   of scope: there is no settings knob whose absence this phase's
   pattern (detect-a-misconfiguration) can meaningfully check —
   building real connection-limiting middleware is a materially larger
   feature with its own risk (breaking legitimate long-lived SSE
   clients without careful design and load testing), not a
   narrowly-scoped addition.
3. **No real KMS/HSM backend.** The seam
   (`governance/crypto/provider.py`'s `KeyProvider` Protocol) already
   exists and is fail-closed-by-contract; only a concrete cloud-KMS
   implementation is missing. Correctly out of scope: cloud-provider-
   specific SDK integration (AWS KMS/GCP KMS/Azure Key Vault, each with
   distinct credentials and failure modes) needs an explicit go-ahead
   naming which provider(s) to target, not a default choice made here.

## Known limitations

`platform_isolation_problems()` currently checks exactly one
condition (DNS rebinding protection). It is deliberately not a
comprehensive platform-hardening checklist — it grows only as real,
checkable gaps are identified, matching `multi_replica_problems()`'s
own scope discipline.

## Unit test results

2 tests in `tests/test_platform_isolation.py`: disabled-transport-
security is flagged, enabled is clean. Both passing. Also re-ran
`tests/test_mcp_server.py`, `tests/test_mcp_http_transport.py`,
`tests/test_mcp_transport_security.py` (93 tests) to confirm the
`_build_http_app()` wiring introduced no regression — all passing.

## Integration test results

The wiring change (`_build_http_app()` calling the new function) is
exercised indirectly by the 93 existing hosted-transport tests above,
none of which regressed.

## Property test results

None new this phase — a two-branch pure function with no numeric or
combinatorial input space doesn't warrant property-based generation
beyond the two example cases already covered.

## Fuzz results

Not run.

## Adversarial test results

Not applicable — this phase adds observability, not a new
security boundary to attack.

## Regression results

Full suite: **3123 passed, 1 skipped, 0 failed**, 127.59s
(`/tmp/full_run_phase12.log`).

## Static analysis

`ruff check`/`ruff format --check`: clean on both the modified
`mcp/server.py` and the new test file. `mypy src/responsibleai`:
clean.

## Dependency audit

No new dependency.

## Secret scan

No secrets introduced.

## Supply-chain results

Not re-run this phase.

## Performance results

Not applicable — one boolean check and a list append at startup.

## Backward-compatibility result

Fully backward compatible. No default behavior changed — the
underlying transport-security default (disabled unless configured)
is unchanged; this phase only adds a log line when that default is
in effect.

## Migration result

Not applicable.

## Rollback procedure

Revert the `mcp/server.py` diff (remove `platform_isolation_problems()`
and its call site) and delete `tests/test_platform_isolation.py`. The
`THREAT_MODEL.md` correction can be reverted independently if ever
needed, though it should not be — it corrects a factual error.

## Documentation updated

`docs/enterprise-neural/12_PHASE12_DESIGN.md`, this report,
`PROGRESS_LEDGER.md`, `CHANGELOG.md`, `THREAT_MODEL.md` (stale-claim
correction).

## Claims now supported by evidence

"A deployer running the hosted MCP transport gets a startup-time
warning if DNS rebinding protection ends up disabled" — true,
evidenced by the tests above and the real wiring in `_build_http_app()`.

## Claims still unsupported

"The MCP transport has application-layer message signing" — false,
by design, named explicitly. "Per-connection SSE DoS protection
exists" — false, named explicitly, `THREAT_MODEL.md`'s own stated gap.
"A real KMS/HSM backend is wired in" — false; only the seam exists.

## Errors found and fixed this phase

A stale claim in `THREAT_MODEL.md` (Section 3): the document said no
upstream MCP proxy executor existed with the same bypass-invariant
property as `InternalToolExecutor`. Phase 11's work (already merged
into this branch) made that false. Corrected as part of this phase's
own "no false claims" mandate — the document's own header invites
exactly this correction.

## Residual risks

The three named gaps (message signing, SSE DoS protection, real
KMS/HSM) remain open, correctly out of this phase's scope but not
silently forgotten — tracked here and in the ledger.

## Next-phase dependencies

Phase 13 (Immutable Audit + Evidence) is next. Given the pattern
across Phases 8, 10, 11, and 12, an audit-first pass is again
warranted — `governance/evidence.py`'s hash-chained `EvidenceRecord`
and `verify_chain()` (Section 3 of `THREAT_MODEL.md`) already exist
and are tested; the one named, real gap
(`ENTERPRISE_SECURITY.md`'s "no external evidence-chain anchoring")
is a plausible starting point for what remains genuinely unbuilt.
