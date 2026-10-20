# M13 cold-restart containment — implementation under qualification

M13 OPEN. GLOBAL PRODUCTION NO-GO. No independent acceptance.

Baseline:bff5f143933d518e921592361f0171d7cf7ff6ef. The proposed0066 is necessary
because process-local files cannot durably prove whether a surviving workload
was started. This candidate does not adopt the preserved stash wholesale.

Hosted sequence:

1. Verify current restore authority and PostgreSQL journal; discover the configured
   daemon read-only. Unknown managed-looking names/labels fence, never authorize cleanup.
2. Commit PREPARING with exact tenant, grant reference, canonical action digest,
   epoch, daemon identity, process generation, unique execution and expected name.
3. Docker CREATE without starting. Require successful reply AND private full CID receipt.
4. Commit ACTIVE with immutable CID. Register revocation/termination ownership.
5. Recheck current organization/epoch, grant expiry and remaining wall budget; START exact CID.
6. Exact-CID cleanup proof precedes CONTAINED. Uncertainty retains UNRESOLVED;
   failed persistence also rotates the process generation, making unfinished intents stale.

New-process admission rejects every nonterminal previous-generation association.
No PID death, elapsed interval, expired grant or missing receipt clears one.
Readiness uses this same durable check even when configured normal READY.

M13 scope is conservative: a single canonical PostgreSQL journal and configured
Docker runtime, with global fencing across process generations. This is not a
cluster-wide daemon-absence proof or an availability/automatic-takeover guarantee.
Old workers/credentials must be retired. Database rollback/loss requires separately
verified Store B and runtime-host fencing. Unknown foreign containers are never killed.

Local storage/protocol tests pass; native SIGKILL/metadata-loss tests and exact
PostgreSQL16 migration proof must run on the new source. Native tests are controlled
component fixtures, not a complete customer/root/identity journey. Expanded crash
points, authorized recovery UX, multi-host fencing and independent review remain OPEN.

Protocol reference: [Docker CREATE](https://docs.docker.com/reference/cli/docker/container/create/)
creates without starting; [START](https://docs.docker.com/reference/cli/docker/container/start/)
is a separate request. This separation, not a quiet-time heuristic, is load-bearing.
