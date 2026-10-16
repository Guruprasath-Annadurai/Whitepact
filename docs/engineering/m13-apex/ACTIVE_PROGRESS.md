# APEX active engineering ledger

M13 OPEN. GLOBAL PRODUCTION NO-GO. No M14/M21 or additional spending.
Current verified checkpoint: `b524ec85710e6b82cc090f079b71b47a4b4ccc13`,
tree `6316d2fdc902033cac25d2c301ceb50f5d88e966`; clean at resumption.
Canonical origin verified; PR216 targets Forge. TITAN PR215 still40e43440,
but its PR base is now `security/whitepact-m13x-platform`; do not assume old base.

| Workstream / issue | Priority / starting state | Reproducer | Files changed / implementation commit | Tests / CI | Independent review | Remaining blocker / next action |
|---|---|---|---|---|---|---|
| Root assurance APEX-ROOT-01 | P0 / blocked | Genuine PostgreSQL HTTP Chromium403 IDENTITY_ASSURANCE_REQUIRED | Existing `tests/js/m13-apex-customer.mjs`, `scripts/engineering/m13_apex_customer_journey.py`;8170a5fddcedac5bd36cf03fbba03a31ebce8f21 |8PASS/1BLOCKED/15NOT_EXECUTED; product CI b524ec85PASS, not root qualification | Pending TITAN-1 | Trace durable verification versus public projection; preserve failing journey; hand exact interface to owner |
| Immutable evidence APEX-EVIDENCE-01 | P0 / historical test changed upstream | Original36 assertions35PASS/1FAIL against40e43440 | No original tests modified | Failure expects0064 after upgrade head now0065; zero skips | Pending explicit independent disposition | Obtain exact blobs, protect historical checkout, compare changed manifest; add separate forward test |
| PostgreSQL APEX-PG-01 | P0 / partial | Unchanged18a upgrade probe c9a4436c->40e43440PASS | No migration changes by Codex | Existing0064->0065 PASS; owner contracts6PASS; retention/downgrade unqualified | Partial, not accepted as whole | Add independent multi-tenant row preservation and explicit downgrade regression |
| TITAN integration APEX-INT-01 | P0 / not integrated | Detached40e43440 source tests | None |35/36 original assertions; owner contracts6PASS | Pending | File-level review; preserve protected originals and manifest; integrate only qualified source |
| Directory APEX-DIR-01 | P1 / repaired metadata, partial coverage | SQLite and real PostgreSQL projections/concurrent claims | `src/responsibleai/trust_fabric/directory.py`, `tests/test_m13_apex_directory.py`;8170a5fddcedac5bd36cf03fbba03a31ebce8f21 | Focused combined49PASS; exact-head product CI b524ec85PASS | Broader acceptance pending | Extend normalization/tombstone/tenant regressions; trace actual consumers |
| MCP APEX-MCP-01 | P1 / repaired external-boundary metadata | Real local HTTP TrustClient call | `src/responsibleai/mcp/tools.py`, `tests/test_m13_apex_mcp_metadata.py`;8170a5fddcedac5bd36cf03fbba03a31ebce8f21 | Combined49PASS; lifecycle7PASS; CI PASS | Provider acceptance pending | Complete supported transports/auth matrix without invented provider evidence |
| CI APEX-CI-01 | P0 / product green, historical failures open | Run38882066529 at b524ec85 | `.github/workflows/m13p4-product-review.yml`;b524ec85710e6b82cc090f079b71b47a4b4ccc13 | Console, contracts3.11/3.12PASS | Product only | Preserve DCO/Gitleaks/Ruff/merge-tree/customer gate dispositions; full mandatory matrix pending |

Next three actions: establish root-assurance contract; preserve exact historical
evidence and test forward migration independently; review selective integration.
External identity proofing and founder300-second PathB policy cannot be fabricated.

## Current closure work (uncommitted until the next checkpoint)

- APEX-ROOT-01 reproduced public BASIC_VERIFIED / root403 mismatch with real HTTP.
 25-stage harness:8PASS/2BLOCKED/15NOT_EXECUTED. See ROOT_ASSURANCE_ROOT_CAUSE.md.
- APEX-EVIDENCE-01 original blob f4d5731e verified in isolated clean detached9fc;
 historical tests2PASS. Upstream revision-specific change reviewed separately;
 original manifest retained. See SECURITY_REPRODUCER_PROVENANCE.md.
- APEX-PG-01 two-tenant0063->0064->0065 data/default preservation PASS.
- APEX-PG-02 P0 newly reproduced nonempty downgrade roundtrip drops passkey
 requirement1->0. BLOCKED for rollback qualification; TITAN migration owner.
 Ordinary row preservation PASS. See POSTGRES_UPGRADE_ACCEPTANCE.md.
- New harness receipt unit regressions4PASS; scoped Ruff PASS before checkpoint.
 Next: owner handoff, commit, then continue directory acceptance independently.

## Signed checkpoint c8ec869cbb7e5e82cfea98033e471b507c93acc9

Root/provenance/PG counterexamples and ledger published. TITAN handoff:
https://github.com/Guruprasath-Annadurai/Whitepact/pull/215#issuecomment-6213967276
Implementation files: `scripts/engineering/m13_apex_customer_journey.py`,
`scripts/engineering/m13_apex_postgres_acceptance.py`,
`tests/js/m13-apex-customer.mjs`, `tests/test_m13_apex_journey_evidence.py`.
Independent security acceptance remains pending; no security integration claimed.

APEX-DIR-02 P1: five malformed claims reproduced then rejected in
`src/responsibleai/trust_fabric/directory.py`. Expanded
`tests/test_m13_apex_directory.py` proves Unicode, recycling and tenant behavior
on SQLite and migrated PostgreSQL. Directory plus receipt run20PASS/0FAIL/0SKIP.
Next commit records this repair and adds APEX triggers to independent CI.
Review status: local regression accepted; broader directory/authority mapping open.
