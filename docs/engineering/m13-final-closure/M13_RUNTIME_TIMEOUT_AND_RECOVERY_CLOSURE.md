# M13 timeout and recovery — OPEN

The former RUN client could die before CID acknowledgement while daemon creation
continued. Repeated name absence cannot establish that creation is finished.

The new protocol sends inert CREATE, verifies the full immutable CID, and only
then permits START after registration/admission. Creation time consumes the original
wall budget; if exhausted, no START occurs and the acknowledged object is cleaned
by CID. Cleanup/reaping may outlast the workload budget; this is not additional
authorized workload time. A transport bound on CREATE is not an absence proof.

The original250ms native soak remains unchanged. New unit cases exercise repeated
timeouts, incomplete acknowledgements, exact-CID cleanup and preparation consuming
the wall budget. Five protocol cases fail on exact bff5f143 and pass on the new
implementation. Mocked cleanup is not physical containment proof.

Creation/acknowledgement failure preserves the private receipt and durable intent.
No guessed name is deleted. Docker/plugin/storage failure preserves uncertainty.
Lost metadata after SIGKILL must be qualified using the new native gate on Linux.

The prior callback test mocks away real cleanup, ESRCH expects unsafe evidence
removal, and restore-FK fixtures retain cross-test uncertainty. Originals remain
unchanged; no replacement test is counted as their PASS. Formal dispositions and
hermetic fixture repairs remain required. No public restore API was activated.
