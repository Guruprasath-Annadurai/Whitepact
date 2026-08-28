# Phase 12 — Platform + Network + Service Isolation: Design

## Objective

Per the master directive's Phase 12 and `00_PHASE0_AUDIT.md` §4's
findings (KMS/HSM key management: not implemented; application-layer
message signing: not implemented, stated gap; per-connection SSE DoS
protection: not implemented, stated gap). Per directive rule 63:
audit first, implement only genuine, well-scoped gaps — this platform
already maintains an unusually honest `THREAT_MODEL.md` naming exactly
these gaps as gaps, not implying mitigation; that discipline is
preserved here, not reset.

## Audit: what THREAT_MODEL.md already documents, verified against real code

- **DNS rebinding protection off by default** (`mcp/server.py`'s
  `_build_transport_security()`): real, current, verified by reading
  the function. `enable_dns_rebinding_protection` only turns on when a
  deployer sets `RAI_MCP_HTTP_ALLOWED_HOSTS`/`RAI_MCP_HTTP_ALLOWED_ORIGINS`
  — a deployer who never configures either gets no protection, with no
  startup-time signal that this is the case. Unlike
  `dashboard/app.py`'s `multi_replica_problems()` (an existing,
  established pattern: a pure, tested function computing
  human-readable misconfiguration findings, logged as a warning at
  startup — not a hard failure), the hosted-MCP transport has no
  equivalent visibility today.
- **No application-layer message signing** (MCP transport): real,
  current. Relies entirely on TLS at the reverse proxy, which is
  explicitly the deployer's responsibility (same posture as the REST
  API, per `ENTERPRISE_SECURITY.md`). Not addressable in-repo without
  inventing a signing scheme the spec doesn't require and no go-ahead
  requested — correctly out of scope.
- **No per-connection SSE timeout**: real, current, confirmed —
  `THREAT_MODEL.md` itself states this has never been load-tested.
  Unlike the DNS-rebinding case, there is no settings knob whose
  presence/absence this phase could check and warn about — the gap is
  "the capability doesn't exist," not "a deployer configured it wrong."
  Building real connection-limiting middleware is a materially larger,
  separately-scoped feature (risk of breaking legitimate long-lived
  SSE clients if done without its own careful design and load testing)
  — correctly out of scope for this phase, named rather than
  papered over.
- **KMS/HSM key management**: `governance/crypto/provider.py`'s
  `KeyProvider` Protocol (Phase 2) is already fail-closed-by-contract
  and backend-agnostic — `LocalEnvelopeKeyProvider` is the only
  concrete implementation today, but the Protocol itself is the exact
  seam a future `KMSKeyProvider`/`HSMKeyProvider` would implement
  without touching any caller. Building a real cloud-KMS integration
  (AWS KMS/GCP KMS/Azure Key Vault, each with its own SDK, credentials,
  and failure modes) is a large, cloud-provider-specific undertaking —
  correctly out of scope without an explicit go-ahead naming which
  provider(s) to target, per directive rule 63.

## A stale claim found and corrected

`THREAT_MODEL.md` §3's "governed MCP dispatch path" entry states:
"this only covers the one executor that exists (`InternalToolExecutor`
...) — no upstream/third-party MCP proxy executor exists yet to have
the same property." This is now false — Phase 11 confirmed
`UpstreamMCPExecutor` exists and has the identical bypass-invariant
properties, independently tested
(`tests/test_citadel_execution_containment.py`,
`tests/test_upstream_gateway.py`). Corrected as part of this phase —
a security document making a claim the code no longer supports is
exactly the "no false claims" violation this whole directive exists to
prevent, and `THREAT_MODEL.md`'s own header explicitly invites this
correction ("if you find a mitigation claimed here that no longer
matches the code... report the discrepancy").

## Genuine, narrowly-scoped gap this phase closes

The DNS-rebinding-protection default-off state has no startup-time
visibility today — a deployer can be unprotected with zero signal,
unlike the `multi_replica_problems()` precedent that already exists
for a different subsystem. This phase extends that exact, established
pattern (pure function, no I/O, unit-testable in isolation; logged as
a warning at hosted-HTTP startup, not a hard failure — consistent with
`multi_replica_problems()`'s own non-blocking precedent) to the
transport-security setting `_build_transport_security()` already
computes.

## Scope for this phase

1. `mcp/server.py`: new pure function `platform_isolation_problems(
   transport_security_enabled: bool) -> list[str]` — returns a
   human-readable finding when DNS rebinding protection ends up
   disabled, empty list otherwise. Wired into `_build_http_app()`
   immediately after `_build_transport_security()` is computed, logged
   via the module's existing `_logger.warning(...)`, mirroring
   `dashboard/app.py`'s `multi_replica_misconfigured` pattern exactly.
2. `THREAT_MODEL.md`: correct the stale `UpstreamMCPExecutor` claim.
3. `tests/test_platform_isolation.py`: unit tests for the new pure
   function (enabled/disabled cases) plus a test proving
   `_build_http_app()` actually logs the warning when transport
   security ends up disabled (using the same `caplog`/structlog
   capture pattern `test_governance_observability.py` or
   `dashboard/app.py`'s own startup tests already use, if one exists —
   checked before assuming the pattern).

No database migration. No new dependency. No change to
`GovernanceServices` or the governance decision pipeline itself.
