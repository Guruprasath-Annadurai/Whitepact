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

## Signed directory checkpoint3ec4317a45caff722d849c440c05d22c3b69ecf3

Product CI38890852085PASS, all3jobs. Independent review38890852102: original36
and extended202PASS on each Python3.11/3.12; native Linux/container15PASS,
zero skips. Overall independent workflow FAIL: genuine customer-origin gate,
inherited101Ruff errors, inherited unsigned ancestor DCO. Gates retained.

APEX-ORG-01 P1 product integration: stale workspace/concurrent rename repaired
selectively from40e43440 with independently verified all-preconditions agreement.
Files: `src/responsibleai/db/org_repository.py`,
`src/responsibleai/dashboard/app.py`, `tests/test_m13_apex_organization.py`.
Implementation commit pending next checkpoint. Independent new+owner tests PASS;
broader19PASS/0FAIL/0SKIP includes PostgreSQL concurrent CAS. Review accepted for
product rename scope only; root/kernel integration pending. Next: commit and
exact-head CI, then MCP/SDK transport and consumer qualification.

## Signed product integration d9bd5b30121e40547083df2e4d9f3afe73d5d463

Tree e6c6c10dba2f19a537aa1291bb42f3cc62d7723a; parent3ec4317a45caff722d849c440c05d22c3b69ecf3.
Product CI38891476380PASS. Independent CI38891476353:36+202PASS perPython,
native15PASS/0SKIP; customer,101Ruff errors and inherited unsigned39619c4b DCO
remain failed gates. GitHub stacked merge162eaa118a2ee393349b1295999f82b86affbe70
has the identical implementation tree; no merge performed.

MCP broad local run518PASS/0SKIP; external SDK consumers3PASS/0SKIP; separate
real framework matrices24PASS and22PASS, zero final skips. See MCP/SDK reports.
APEX-SDK-02 P1: combined pinned environment has incompatible OpenAI constraints;
separate environment qualification accepted, co-installation BLOCKED. No pins
weakened. Provider doc reconciliation pending next documentation checkpoint.

TITAN has advanced to e1a9f1235d6b46b7423c21815ff27ebebf6887c6; separate clean
review checkout created. Original migration blob and manifest restored upstream.
Independent genuine journey, original assertions and new owner-authored contracts
are running. TITAN-2f439553d is a report-only descendant of40e43440; its reported
results are owner evidence, not copied into Codex independent counts.

## Root failure checkpoint1fd55ed536d4476657eca31463834e7356043951

| Workstream / issue | Priority / starting state | Reproducer / changed files | Implementation SHA | Tests / CI | Independent review | Remaining blocker / next action |
|---|---|---|---|---|---|---|
| Root principal binding APEX-ROOT-02 | P0 / actual completion500 | Fresh e1a9 journey, FK `trust_fabric_trust_roots_root_principal_id_fkey`; `scripts/engineering/m13_apex_customer_journey.py`, `tests/test_m13_apex_journey_evidence.py` |1fd55ed536d4476657eca31463834e7356043951 |10PASS/1FAIL/14NOT_EXECUTED; diagnostic principal_count0; receipt6PASS; final CI pending | Security implementation not accepted | TITAN-1 must establish real tenant-scoped principal binding; no fixture insertion |
| Root identity APEX-ROOT-01 | P0 / earlier403 | Real e1a9 basic-email qualification/initiation now200 | Owner e1a9f1235d6b46b7423c21815ff27ebebf6887c6; not integrated | Owner contracts15PASS, original35PASS/1head-versionFAIL | Narrow initiation improvement independently observed | Do not equate basic email with external proofing; overall root remains blocked |
| Evidence APEX-EVIDENCE-01 | P0 / changed upstream original |8original blobs match unchanged manifest; isolated9fc checkout | Restored by owner e1a9f1235d6b46b7423c21815ff27ebebf6887c6; APEX never replaced it | Original migration2PASS on9fc; known newer-head assertion retained | PRESERVED, intervening change REVIEWED_CHANGE | Keep revised forward tests separate; do not fake original test PASS |
| SDK co-install APEX-SDK-02 | P1 / optional dependencies skipped | Combined pinned resolver incompatible; separate disposable envs | Product source d9bd5b30121e40547083df2e4d9f3afe73d5d463 unchanged | Separate24PASS+22PASS/0SKIP; packages3PASS; initial32skips retained | Separate environments accepted only | Shared environment BLOCKED on OpenAI2.x/3.x conflict; keep pins |

Current owner handoff:
https://github.com/Guruprasath-Annadurai/Whitepact/pull/215#issuecomment-6216956340.
Next three actions: publish full report/current receipts; run final exact-head
CI/scans and genuine failure diagnostic; incorporate only owner-qualified root
binding/rollback contracts after independent acceptance. No approval flow bypass.

## Additional CI regression APEX-CI-02

P1 / starting state2FAIL+12PASS in mutable startup suite: obsolete0063 literal
after real `upgrade head`. Files changed: `tests/test_db_migrate.py`,
`.github/workflows/m13p4-product-review.yml`. Compare real DB revision to the
single declared canonical head; preserve all immutable original test/hash files.
Implementation SHA recorded in next signed checkpoint receipt. Scoped Ruff and
format PASS; full14-case runs against APEX0064 and detachedTITAN0065 in progress.
CI:5a02 productPASS, independent original/extended/nativePASS with3retained
policy/customer failures, CodeQLPASS, full-historyGitleaks6findingsFAIL; new-head CI pending.
Independent review: legitimate mutable-test scope maintenance, not protected
evidence replacement. Next action: retain results, commit, re-run exact-head CI.

Verification complete: startup14PASS onAPEX (42.31seconds),14PASS onTITAN0065
(34.97seconds), zero skips,2deprecation warnings each. The intermediate
cross-worktree fixture resolved a relative scripts directory against harness CWD;
fixed to resolve relative to the selected candidate ini. No production migration
logic changed. Protected originals and manifest unchanged. Owner policy handoff:
https://github.com/Guruprasath-Annadurai/Whitepact/pull/215#issuecomment-6217172171.
