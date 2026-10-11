# Enterprise qualification candidate

This file is the engineering handoff. It is not an Antigravity verdict
and not a production authorization.

The previous independent audit was PR #179 at commit
`15091d6aec6f84b3e1c8b653db7855074372694d`, tree
`cecf25188fdcb3fc094200f4bdf6e8d2f4e47f22`: 59 of 73 passed, 3 failed,
11 blocked or unverified, 80.8%, production NO-GO. That score is not
reused. This tree is different.

Identify the handoff with `git rev-parse HEAD` and `git rev-parse
'HEAD^{tree}'` on the qualification branch. A SHA written here would be
stale after the commit that adds this file.

## Three outcomes

### A. Engineering completion

Implemented and locally exercised:

- DEF-01. Portable runner tests stub ACL only for runner selection.
  `test_linux_workspace_acl_grants_container_uid` uses real `setfacl`
  and `getfacl -n`. It passed on this Linux host.
- DEF-02. Non-Linux hosts skip nftables and nginx with
  `QUALIFICATION_SKIP`. Linux fails if `nft`, `ip`, or the nginx tools
  are missing. Both the nftables namespace test and the nginx client
  certificate test passed here.
- DEF-03. Ruff on `src/`, `tests/`, and `sdk/python/` passes. Markdown
  is excluded. Migrations were not mass-formatted.
- Evidence publication outside the database, including tamper detection.
  Live R2 is not provisioned.
- Redis rate-limit scores use wall time. Two clients shared one local
  Redis. CI now starts Redis and sets `WHITEPACT_REQUIRE_REDIS=1`.
- Tenant audit CSV export returned only the caller org, with
  `entry_hash` and `prev_hash`.
- Security inclusion uses AST for `test_*` names. A second script
  executes the regression tests and fails if one is skipped. That
  script passed, 13 tests, 0 skips.
- Offline Terraform validate for the Hetzner and Cloudflare modules.

Not engineering-complete:

- Database-backed and HTTP performance against an approved SLO.
- Browser onboarding journey on this tree.
- Live backup restore, failover, and alert delivery.
- Any cloud account.

No percentage is assigned. The unfinished items are blockers, not a
fraction of a pass.

### B. Independent qualification

Antigravity has not reviewed this tree. Independently passed mandatory
criteria: 0. The historical 59 passes are void for this tree.

### C. Enterprise production authorization

NO-GO. Live security and operational gates are not satisfied.

## Category baseline

The 73-criterion shape is kept. Counts below are not an independent
score. "Local" means an engineer ran a test on this host.

| Category | Applicable | Independent pass | Local engineering note |
| --- | --- | --- | --- |
| core_governance | 8 | 0 | P0 admission and resume tests passed in the regression script. Not independently retested. |
| security_hardening | 8 | 0 | ACL, nftables, nginx, and witness tests passed locally. Live anchor blocked. Docker daemon skipped. |
| mcp | 6 | 0 | Metering regression passed locally. No external MCP client certification. |
| enterprise_saas | 8 | 0 | Billing provider not configured. |
| api_sdk | 6 | 0 | Ruff includes `sdk/python`. No new wheel-publish or SDK journey. |
| dashboard | 6 | 0 | No browser journey on this tree. |
| performance | 4 | 0 | Kernel microbenchmark only. SLOs unapproved. |
| cloud_infrastructure | 6 | 0 | Validate only. Apply blocked. |
| live_operations | 6 | 0 | No restore or failover drill. |
| enterprise_acceptance | 15 | 0 | Audit export HTTP test passed locally. Scenarios that need a live IdP or browser were not run. |

## Previously soft passes

| Claim | Correction |
| --- | --- |
| Audit export | A 503 is only safe failure. This tree adds an HTTP test that exports org A and asserts org B is absent. Still one process and SQLite, not a customer SIEM. |
| Failure and recovery | Not reclassified as recovered. No restore drill ran. |
| Distributed limiting | In-memory limiting is not the claim. One Redis process and two clients passed. Multi-host production is still unverified. |
| Customer journeys | The new test is an API path. It is not a browser walkthrough. |
| Performance | The kernel number is labeled not-an-HTTP-SLO. |
| Security mocks | Runner mount tests stub ACL and say so. The ACL test does not stub `setfacl`. |

## Release decisions

| Decision | Status |
| --- | --- |
| Directory listing | Not submitted. Do not list. |
| Open-source release publication | Not authorized. Do not publish. |
| Controlled enterprise evaluation | Possible only as a source review of this NO-GO candidate. Not a production pilot. |
| Global enterprise production | NO-GO. |

## Owner decisions still required

1. `APPROVE STAGING CLOUD PROVISIONING` or an explicit refusal. Without
   it, C1–C7 stay blocked.
2. Fund Hetzner and Cloudflare, or name a different approved provider
   that must meet the same isolation tests.
3. Create the R2 object-lock bucket and a put-only token, then schedule
   an independent read-back.
4. Approve or reject the SLO table in `PERFORMANCE_SLO_PROPOSAL.md`.
5. Authorize Antigravity to qualify this exact tree. Do not merge, tag,
   or publish ahead of that review.
