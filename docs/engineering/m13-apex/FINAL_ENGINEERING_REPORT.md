# M13 APEX engineering report — PARTIAL / GLOBAL PRODUCTION NO-GO

## 1. Executive verdict

**Full M13 acceptance gates are not satisfied.** Stronger product and independent
verification checkpoints are published in [draft PR216](https://github.com/Guruprasath-Annadurai/Whitepact/pull/216).
The genuine customer root remains unqualified. Milestone M13 OPEN; M14/M21 prohibited.

## 2. Repository and exact implementation provenance

Canonical origin https://github.com/Guruprasath-Annadurai/Whitepact.
Branch `codex/whitepact-m13-apex-integration`, isolated worktree
`/private/tmp/whitepact-m13-apex`. Tested product implementation checkpoint:
HEAD d9bd5b30121e40547083df2e4d9f3afe73d5d463,
tree e6c6c10dba2f19a537aa1291bb42f3cc62d7723a,
parent3ec4317a45caff722d849c440c05d22c3b69ecf3.
This report and subsequent harness/receipt changes are packaged in a later
signed checkpoint; its exact HEAD/tree/parent and exact-head CI are recorded in
the PR216 checkpoint receipt, avoiding a self-referential Git commit hash.

## 3. Integration ancestry

APEX starts at Forge9fc9f94873d645ce36239e44eef6919a8604bdc7.
Product-only organization rename repository/adapter selected from TITAN40e43440,
with independent conflict validation. No whole security-branch merge. Root,
consent, delegation, revocation and runtime security changes remain unintegrated.
GitHub stacked merge162eaa118a2ee393349b1295999f82b86affbe70 had exactly the
d9bd5b30 implementation tree and parents Forge9fc +d9bd5b30. No merge performed.

## 4. Feature completion matrix

| Feature | Evidence / limit |
|---|---|
| Signup, email, password, organization | Actual fresh candidate customer stages pass |
| First passkey, UV, session rotation | Actual Chromium candidate ceremonies pass; virtual authenticator only |
| Identity qualification | New TITAN basic-email status recognized; no external proofing claimed |
| Root, scoped consent, PoP activation | FAIL on real PostgreSQL missing-principal FK; not accepted |
| App/agent/delegation/policy | Fixture regressions only; genuine same-lineage stages NOT_EXECUTED |
| Judgment/approval/grant/execution | Genuine journey NOT_EXECUTED; fixture outcomes not substituted |
| Revocation/denial/evidence/recovery | Regression subsets pass; complete genuine customer chain unqualified |
| Directory | Metadata, normalization, tenant, concurrency and recycling qualified locally; UI canonical mapping open |
| Organization rename | Product integration PASS with session/CSRF/role and PostgreSQL concurrency |
| MCP |518 local regressions PASS; no real provider acceptance inferred |
| SDK packages | Python/TypeScript/Go external consumers3PASS; no publishing |
| Frameworks | Separate pinned real-object matrices24PASS and22PASS; shared install incompatible |
| Responsive/accessibility/account | Preserved Forge console and current product CI pass; no full privileged customer acceptance |

## 5. Defects eliminated

8170a5fd: directory metadata loss and inaccurate MCP outbound-world hint.
3ec4317a: malformed identifier claims, with Unicode/tombstone/tenant regressions.
d9bd5b30: stale workspace/name rename and contradictory precondition acceptance.
c8ec869c and later harness checkpoint: independent root/PG counterexamples,
exact25-stage receipts and contract-aware receipt validation. Tests are evidence,
not standalone declarations of feature completion.

## 6. Open P0/P1 defects

APEX-ROOT-02 P0: missing real tenant-scoped canonical principal binding ->root500,
TITAN-1 owner. APEX-PG-02 P0 rollback qualification:0065->0064->0065 loses required
passkey flag1->0; TITAN migration owner disposition required. Full root/security
integration acceptance incomplete. APEX-CI-01: inherited101Ruff errors, unsigned
39619c4b ancestor and customer gate remain failed. APEX-SDK-02 P1: incompatible
OpenAI requirements in combined pinned framework environment. Directory app/agent
binding and provider account acceptance remain open. Founder300-second PathB
policy remains pending; no policy decision inferred.

## 7. Independent security verification

e1a9f1235d6b46b7423c21815ff27ebebf6887c6,
tree cd74e5efe91c61ec2d871525d244d39268bead9e: owner-authored closure/adversarial/
migration/contracts15PASS in271.39seconds. Preserved original assertions35PASS,
1FAIL (0064 expectation versus0065 head), zero skips,177.21seconds. These were
executed independently, not copied from TITAN-2's report. No blanket acceptance.

## 8. PostgreSQL

Original18a probe PASSed existing c9/0064->40e/0065. Separate actual PG16.15 probe
retains two tenants' organization/bootstrap/recovery rows through0063->0064->0065,
with non-null defaults. Nonempty downgrade loses security flag; not qualified.
Concurrent-startup and broader historical-version acceptance remain incomplete.
See POSTGRES_UPGRADE_ACCEPTANCE.md; fixture rows are not customer authority.

## 9. Identity assurance

Earlier projected BASIC_VERIFIED versus stored status mismatch reproduced and
handed to TITAN. New e1a9 recognizes basic email assurance. Root still fails
without canonical principal binding. No provider event, identity record or ACTIVE
principal fabricated. See ROOT_ASSURANCE_ROOT_CAUSE.md.

## 10. Genuine25-stage journey

On detached e1a9, actual browser/HTTP/PostgreSQL journey reaches root initiation,
then root completion fails500 on a real FK. Ten phases PASS, one FAIL, fourteen
NOT_EXECUTED. No consent/root success, delegated authority, actual execution or
revocation success counted. Logout invalidation passes. No retry of the same
consequential action; repeat diagnostics use entirely fresh identity/database.
Read-only diagnostic confirms zero canonical principal rows. Owner fixture
full-chain tests insert an ACTIVE principal and later disable required stepup;
they do not satisfy this customer gate.

## 11. Universal Directory

See UNIVERSAL_DIRECTORY_ACCEPTANCE.md. Combined directory/receipt run20PASS and
later organization/directory/receipt run19PASS, zero skips; counts overlap and
must not be summed as unique coverage. Decision/passport consumers found;
direct customer dashboard canonical-directory integration not established.

## 12. MCP/provider compatibility

518PASS/0SKIP,8warnings,697.67seconds on mcp1.29.1; actual local transport subset
distinct from mocked/fixture assertions. See MCP_PLATFORM_ACCEPTANCE.md and
AI_PLATFORM_COMPATIBILITY.md. All named provider current-head acceptance remains
BLOCKED or NOT_TESTED. Official docs reviewed; historical receipts preserved,
not promoted to current verification. No hosted activation or listing submission.

## 13. SDK and framework acceptance

External Python wheel, TypeScript ESM/CommonJS tarball and network-disabled Go
consumer3PASS/0SKIP,109.31seconds. Separate Wave1 matrix24PASS/0SKIP and
CrewAI/LlamaIndex22PASS/0SKIP. Combined pinned environment resolver conflict
preserved; no version pin weakened. See SDK_INSTALLATION_COMPATIBILITY.md.

## 14. Enterprise SaaS acceptance

Existing console/account/accessibility tests and build pass current product CI.
Rename product tests independently reject unauthenticated401, missing-CSRF403,
viewer403, stale/conflicting context409 and concurrent name changes409.
Real PostgreSQL compare-and-set has one winner. No inactive capability made
usable; no privileged UI enabled to bypass incomplete backend contracts.

## 15. Linux/runtime isolation

Actual Ubuntu runner/container scope15PASS, zero skips,108.15seconds atd9bd5b30.
This is native runner evidence, not macOS skips or copied TITAN-2 counts.
Multi-host/external witness qualification not established; no cloud resources.

## 16. Evidence and audit

Regression scopes cover nonce/revocation/egress and controlled SDK outcome
preservation. No actual accepted customer execution means no complete customer
execution/evidence/audit chain is claimed. Durable distributed/external-witness
acceptance remains open.

## 17. Exact-head CI and policy disposition

[Product38891476380](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38891476380)
atd9bd5b30: console and Python3.11/3.12 contracts PASS.
[Independent38891476353](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38891476353):
36 original+202 extended PASS on each Python version; native15PASS. Overall FAIL
for customer, inherited101Ruff errors and unsigned39619c4b DCO. Original customer
gate remains failed, not rewritten to accept a blocked journey. Main-base-only
workflows do not automatically run for stacked Forge PRs; their absence is not
success. Historical Gitleaks/CodeQL aggregate issues require fresh scan or formal
owner disposition. No policy exclusions, forged signoffs or history rewrites.

## 18. Reproducer integrity

All8 original test blobs match the unchanged SHA manifest in APEX. Isolated
historical9fc checkout tests2PASS. New e1a9 restores original test and manifest
upstream. Revision-sensitive migration coverage is separate. See
SECURITY_REPRODUCER_PROVENANCE.md. Restored integrity is not a passed original
head assertion against0065.

## 19. Skips and unavailable acceptance

Final broad MCP, isolated framework, SDK-package and native scopes have zero skips.
Initial framework run14PASS/32SKIP is preserved separately; later isolated runs
resolve those dependency skips. Intermediate environment/receipt-validator errors
are retained as harness errors. Real provider accounts, external proofing,
multi-host witnesses, full consequential journey, nonempty rollback and founder
PathB policy remain unavailable/unqualified; none counts as PASS.

## 20. Gate and launch conclusion

CheckpointA PARTIAL; B/C BLOCKED; D PARTIAL; E BLOCKED. Release-readiness score
**1/10** on a gate-based rubric (0=no supporting evidence,10=all mandatory gates
satisfied): core product/regression evidence exists but real authority activation,
execution chain and policy closure are absent. This is not a test-pass percentage.
**NO-GO. Full M13 acceptance is not satisfied.** No main merge, deployment, DNS,
paid services, provisioning, package publication, M14 or M21 execution occurred.

## Subsequent exact-head receipts and startup-test maintenance

At5a02bf4d30830284f1650f94ae4a634a7315e7f6 (tree
cba08437caa9f8db1c08b953aea7e8b3ed879426), the clean committed harness repeated
the e1a9 genuine failure: user exists, canonical principal0, root records0,
consent records0. The unchanged18a probe again PASSed c9/0064->e1a9/0065.
CodeQL38911491837 PASSed both Python and JavaScript/TypeScript analysis;
Gitleaks38911486998 FAILED with6full-history findings. One proven type-annotation
match contains no string literal; two entity-key fixture matches are outside
candidate ancestry. Remaining findings require owner triage; no allowlist,
history rewrite or blanket false-positive dismissal was applied.

The mutable `tests/test_db_migrate.py` independently reproduced2FAIL/12PASS
against e1a9: startup correctly reaches0065 but two tests expected0063. These
non-manifest tests now compare actual database revision with the independently
loaded single declared Alembic head. Fresh/idempotence/no-false-stamping assertions
remain; immutable original migration evidence is untouched. The suite is added
to product CI with scoped lint/format checks. This exercises SQLite startup
paths; it does not claim PostgreSQL concurrent-startup qualification. New
checkpoint CI and final Git provenance are attached to PR216's latest receipt.

Startup verification:14PASS/0SKIP onAPEX0064 and14PASS/0SKIP on detachedTITAN0065,
with2deprecation warnings each. A cross-worktree test-fixture path mismatch was
corrected by resolving the relative migration scripts against the selected ini's
directory. No application migration logic or original immutable test was edited.
Supply-chain owner handoff:
https://github.com/Guruprasath-Annadurai/Whitepact/pull/215#issuecomment-6217172171.

Further selective integration APEX-MCP-02: new TITAN-2 6b604bf1 adds actual SSE
session credential binding. Independent real-TCP test reproduces unauthenticated
ping202 on old APEX and verifies owner-only messaging plus missing/invalid/foreign/
sibling/revoked denial on candidate. Selected server blob is byte-identical to
reviewed owner; integrated subset85PASS/0SKIP. SDK floor1.29.1 matches qualified
APIs; full519 MCP cases are required on both independent Python CI jobs. Other
TITAN-2 nonce/runtime/container changes remain unintegrated. See selective review;
final exact-head CI receipts must qualify this new checkpoint separately.
