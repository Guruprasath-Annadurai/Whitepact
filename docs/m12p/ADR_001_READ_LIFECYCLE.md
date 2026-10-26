# ADR M12-P-001: bounded reads, one-shot mutations and current read snapshots

Status: product implementation proposal; independent review pending.

## Context

The browser API client allowed reads to stall indefinitely and accepted invalid
successful JSON as null. Approval detail reads duplicated repeated IDs and stale
responses could overwrite a newer list snapshot, showing obsolete controls.
Unit regressions reproduced these failures before fixes.

## Decision

GET/HEAD reads have a 15-second deadline, composed with caller cancellation.
No automatic retry occurs. Explicit retry starts a new read. Timers/listeners
are released on settlement. Mutations do not gain automatic retries or a timer
that could be confused with proof of non-execution. HTTP error status survives
invalid error JSON; malformed successful JSON produces a fixed, private error.
An uncertain mutation remains uncertain under the existing outcome classifier.

Approval detail reads are deduplicated within one returned list snapshot, not
cached across refreshes. Obsolete reads are aborted and their late responses
ignored even if a transport disregards abort. Controls and confirmations are
bound to the currently displayed snapshot; the server still independently
authorizes every vote/execution. No client permission decision is created.

## Consequences and verification

Deterministic repeated-ID case reduces detail requests from two to one. This is
a request-count result, not a latency/throughput or production-scale claim.
Read timeout bounds normal fetch/body cancellation, not an arbitrary third-party
mock that ignores AbortSignal. No stale revocation/approval authorization cache.
Regression tests cover read timeout/retry/cancellation, malformed success/error,
missing context, stale reads, changed confirmations and mutation uncertainty.
Real browser fixtures and real backend tests are reported separately.

Implementation is original AI-assisted product engineering under existing
license/provenance conventions. No security primitive or cryptography reinvented.
