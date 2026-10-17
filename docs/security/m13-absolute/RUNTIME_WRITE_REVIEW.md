# Absolute runtime correction — independent review required

Base: TITAN-2 `622b02d6d52b6467204f0464bda9252a65606e33`.
This isolated proposal does not qualify the integrated APEX candidate or customer authority.

Independent counterexamples on byte-identical base implementation: five failures
(rejected admission cancellation, lost unresolved tracking, plugin inspect errors,
and the two unchanged cancellation reproducers). A separate contended-registry
counterexample against the pristine owner worktree also failed. Local receipts:
`/private/tmp/apex-absolute-runtime-owner-red.log` and
`/private/tmp/apex-absolute-runtime-contention-red.log`.

The correction preserves actual cancellation request counts while awaiting owned
cleanup and final registry transitions. Rejected admissions retain unresolved
termination evidence unless termination is confirmed; the registry does not cancel
its own caller. The production termination callback rejects plugin/daemon errors
as evidence of absence. Registration rechecks revocation under its registry lock.

Focused local validation: 18 passed; neighboring revocation/runtime validation:
35 passed. These use controlled subprocess responses and are not native Docker
proof. The dedicated workflow additionally exercises actual Linux Docker lifecycle,
two cancellation requests, and injected CLI failure with independent real-container
inspection. Native results must be read from the committed exact-head CI run.

The original migration reproducer is restored verbatim to blob
`f4d5731e9b2792b18a69e1fcfd475164ee4f0898`; its historical head-0064 expectation
is not silently rewritten to accept head 0065. The unchanged dual-cancellation
reproducer blob is `bc00c78e9cafa461b58cde388610b43c5866acfe`.

Remaining owner review: durable tracking after process death and tracking-write
failure, canonical execution outcome after an unresolved cleanup, registry-lock
recovery deadlines, and historical runtime/schema compatibility. This change
does not certify those contracts or resolve founder-controlled identity policy.

M13 OPEN. GLOBAL PRODUCTION NO-GO.
