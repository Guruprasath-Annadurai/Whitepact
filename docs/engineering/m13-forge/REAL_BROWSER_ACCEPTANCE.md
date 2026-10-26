# Browser acceptance

`scripts/engineering/m13_forge_browser_journey.py` adds a stage journal around the original actual I3 PostgreSQL/HTTP/CDP harness. `tests/test_m13_forge_browser_evidence.py` tests evidence integrity only; it is not authentication evidence.

Original I3 harness and all historical security counterexamples are preserved unchanged. Fresh runtime at clean `0df19a2d392c1243396242fc905a2aa7fb5ac545` / tree `9f3b835f8aa3aa11bdad02ec5cac7a7123e90a05`: 10 stage PASS, origin binding BLOCKED (`RP_OR_ORIGIN_CONTRACT_MISMATCH`), remaining authority actions NOT EXECUTED. Zero credentials persisted; logout confirmed. Raw redacted report: `/private/tmp/forge-browser-checkpoint1.json` (temporary local evidence; PR receipt carries durable summary).

Do not interpret browser emulation as physical hardware qualification or an HTTP prefix as a complete visual workflow.

The separate existing CI browser fixture journey now passes end-to-end on fresh PostgreSQL after fixing outcome retention, summary display serialization and its stale editable-organization expectation. It verifies success/evidence, UNKNOWN reconciliation without replay, denial, persisted summary types, read-only organization, key revocation, policy persistence and post-logout 401. This fixture explicitly seeds development authority and uses an identity webhook fixture; it does not replace or qualify the unseeded customer ceremony. Earlier fixture runs failed at each discovered contract mismatch and remain failed evidence.
