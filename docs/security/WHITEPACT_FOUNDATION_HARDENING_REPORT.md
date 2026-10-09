# WHITEPACT — CURSOR COMPLETE FOUNDATION SECURITY HARDENING REPORT

This is foundation hardening. It is not a launch GO, not a production-readiness claim, and not an independent qualification. Antigravity has not signed this delta.

## A. Repository HEAD/TREE and branch inventory

Inspected before any edit:

| Ref | SHA | Role |
| --- | --- | --- |
| `origin/main` | `38f927229b4ea53d19a9107c78653307f5263629` | Merged cloud-bootstrap tip. Tree `90ff06908d8687200fdc6a3e55f161355418f7b2`. Behind the launch candidates. |
| PR #169 `cursor/whitepact-global-launch-execution-d20d` | `d2f5405e9c31e6b5676c1c327e4c1de2c0379e56` | Matches the historic reference. Ancestor of this work. |
| PR #170 `cursor/whitepact-successor-qualify-b6a9` | `996795adeac0adbad9eec9c9ca51e2f8aa4c80fc` | Matches the historic reference. Ancestor of this work. |
| PR #171 `cursor/whitepact-canonical-reconcile-d20d` | `6801d4ad0047d15a196ab9caeffacf54f9ce557e` | Matches the historic reference. Ancestor of this work. |
| PR #172 `cursor/whitepact-phase3-preflight-b6a9` | `7a0852899afd997264c384a9ff5ca5f99a65c7ca` | Current tip. Historic note `6fefece7b7620ae2f1fa7c307f6720e4bbde709f` is the parent of the docs commit that moved the tip. Tree at branch point `1262198173e52df94c7c85d75ea24a02e6da7e99`. |

Hardening branch: `cursor/whitepact-foundation-hardening-934e`, created as a separate worktree at `/workspace/hardening` from `7a0852899afd997264c384a9ff5ca5f99a65c7ca`. Draft review: https://github.com/Guruprasath-Annadurai/Whitepact/pull/174 against `cursor/whitepact-phase3-preflight-b6a9`. Launch-candidate histories were not rewritten. This branch is not merged.

`origin/main` does not contain the qualified memory-scope and evidence commits. Hardening was stacked on the preflight tip so those protections stay in the tree. The review diff is against that preflight branch, not against `main`.

## B. Execution and trust-boundary graph

Governed hosted path that this change re-checked:

Request (Streamable HTTP `/mcp` or legacy SSE `/sse`) → Bearer authentication (`_authenticate_or_error`, shared failure limiter) → `OrgContext` from OAuth, OIDC, VC, or org API key → hosted flag and governance services → `_call_tool` refuses missing org, legacy context, or missing governance → purpose required → `apply_governance` → authority, policy, approval, evidence (fail closed on evidence write) → trust enrichment when provider/model are present → `WhitePactRuntimeGateway.evaluate` → `ExecutionAuthorization` → `InternalToolExecutor.execute` or `UpstreamMCPExecutor.execute` → effect → outcome evidence.

Dashboard REST: `get_org_context` resolves the credential, records `request.state.audit_org_id`, then route limits key by that organization. Authentication failure limiting is IP-keyed and, in production, durable in PostgreSQL. Plan changes from Paddle update commercial columns only. `apply_paddle_entitlement` is not consulted by Trust, authority, policy, or `ExecutionAuthorization`.

Intentionally ungoverned: community stdio. Enterprise trust domain still refuses that mode. This change does not alter community stdio semantics.

Library imports of engines remain outside the mediated boundary. That is a stated gap, not a new bypass.

## C. Security-sensitive surface touched

- Authority host egress: `infra/terraform/modules/whitepact-hetzner-foundation/locals.tf`
- Gateway trust admission: `src/responsibleai/governance/gateway.py`
- Policy shadow rejection: `src/responsibleai/governance/policy.py`, `src/responsibleai/db/policy_repository.py`, `src/responsibleai/governance/policy_lifecycle.py`
- Rate-limit identity: `src/responsibleai/dashboard/app.py`, `src/responsibleai/mcp/server.py`
- Multi-replica production refusal: `src/responsibleai/dashboard/config.py`
- Evidence claims and offline witness: `src/responsibleai/db/evidence_repository.py`, `src/responsibleai/governance/attestation.py`, `src/responsibleai/governance/evidence_witness.py`, `src/responsibleai/dashboard/web_governance_contracts.py`

Preserved, not reopened: memory-scope delegation denial already on this ancestry (`d4bad2e`, `74e6262`), enterprise stdio refusal, hosted production preflight.

## D. Confirmed findings

| ID | Severity | Status |
| --- | --- | --- |
| FH-01 | P1 | Fixed. Authority output chain accepted every TCP/443 destination when NAT was enabled, after the allowlist rules. nftables is first-match, so `authority_egress_cidrs` did not constrain backup egress. |
| FH-02 | P1 | Fixed. A Trust Index outage stored `TrustCheckResult.error` and the gateway still returned ALLOW for an otherwise permitted action. A successful unknown model was, and remains, non-escalating. |
| FH-03 | P2 | Fixed. Dashboard route limits keyed by bearer-token hash, so key rotation multiplied the organization ceiling. Authenticated keys now use `org:<id>`. |
| FH-04 | P2 | Fixed. Hosted MCP auth-failure limiter defaulted the peer ceiling to 50 while the credential ceiling was 10. Rotating bearer tokens from one address multiplied attempts. The peer ceiling now equals the credential ceiling. |
| FH-05 | P2 | Fixed. A later DENY or approval rule fully covered by an earlier weaker rule could be stored and would never fire. Persistence and revision creation now reject that shadow. A narrower ALLOW before a broader DENY is still accepted. |
| FH-06 | P2 | Claim corrected, live gate open. The database hash chain was described as if recomputation proved integrity against a rewriting database administrator. Wording now states the limit. An offline Ed25519 head witness verifies a head the signer saw. Live publication is not deployed. |
| FH-07 | P2 | Fixed. Production with `multi_replica` and non-shared SQLite or in-memory rate limits only logged a warning. Startup now raises. Non-production still warns. |

No confirmed exploitable P0 was left open in the paths above. This is not a claim that no other P0 exists.

## E. Reproductions and root causes

FH-01. `locals.tf` appended `tcp dport 443 accept` whenever `enable_nat_gateway` was true. Isolated nftables in a network namespace: that rule’s counter incremented for `203.0.113.10:443`. After removal, the same destination did not match the allowlist counter, and `10.255.0.1:443` did. Root cause: a backup convenience accept sat after the allowlist in a first-match drop chain.

FH-02. `TrustClient.check` records transport failure as `error` with `known=False`. `_trust_reason` returned None for every `known=False` result, including errors. Root cause: outage and unknown model shared one branch. The error branch now requires approval (`TRUST_LOOKUP_UNAVAILABLE`). `tests/test_governance_trust_state.py` covers both.

FH-03. `_get_rate_limit_key` hashed the bearer token. Two tokens for one `audit_org_id` now return `org:<id>`.

FH-04. `_AuthFailureLimiter` peer default was 50. Hosted construction now passes `peer_max_failures` equal to the credential maximum. A second bearer token from the same test client receives 429 after the budget is spent.

FH-05. `Policy.evaluate` is first-match. Append and reorder stored a stricter rule behind a covering weaker rule. `reject_shadowed_restrictive_rules` runs before insert, reorder, and revision create. Duplicate DENY rules are not treated as a bypass.

FH-06. `verify_chain` recomputes stored hashes. An attacker who rewrites rows and recomputes those hashes still passes. `sign_evidence_head` / `verify_evidence_head` bind org, sequence, and head hash. A substituted head fails. `LIVE_ANCHOR_STATUS` is `EXTERNAL_BLOCKER`.

FH-07. Lifespan called `multi_replica_problems` and only logged. `enforce_shared_backends_for_multi_replica` raises in production when that list is non-empty. The lifespan calls it.

## F. Remediation files

Code and tests on `cursor/whitepact-foundation-hardening-934e`, parent `7a0852899afd997264c384a9ff5ca5f99a65c7ca`:

- `cdef4c7` fix(net): keep authority HTTPS on the egress allowlist
- `2bccc8b` fix(governance): require approval when trust lookup fails
- `29f8b24` fix(policy): reject stricter rules hidden by an earlier match
- `06093e1` fix(security): stop key rotation from multiplying ceilings
- `bfbd9af` fix(evidence): do not treat a recomputed hash chain as an external witness

Changed areas are the files in section C plus:

- `tests/test_foundation_hardening.py`
- `tests/test_governance_trust_state.py`
- `tests/test_mcp_transport_security.py`
- `docs/enterprise/cloud/CLOUD_HOST_FIREWALL_POLICY.md`
- `THREAT_MODEL.md`
- this report

No Terraform apply. No production deploy. No PyPI publish. No merge.

## G. Attack suite, positive cases, and negative cases

Negative:

- Non-allowlisted HTTPS from the authority output policy is not accepted.
- Trust Index connection failure does not ALLOW.
- Shadowed DENY is not persisted and is not created as a policy revision.
- Rewritten evidence head fails witness verification.
- Rotated API tokens share one organization rate-limit key.
- Rotated MCP bearer tokens do not reset the source failure budget.
- Production multi-replica without PostgreSQL and Redis is refused by the shared-backend check.

Positive:

- Allowlisted `10.255.0.1:443` matches the accept counter.
- Successful unknown-model trust result still ALLOWs.
- Specific ALLOW before a broader DENY is not classified as a shadow.
- A high-risk DENY plus a separate read ALLOW both persist.
- A correctly signed witness verifies.
- Community stdio refusal and enterprise trust-domain tests in the regression set still pass.

## H. Python, CI, coverage, and build evidence

Python 3.12.3, pytest 9.1.1, focused run: `15 passed` in `tests/test_foundation_hardening.py`, trust lookup failure, and MCP token rotation. Broader run of foundation, trust, MCP transport and enterprise trust domain, policy repository/activation/rollback/revision, cloud origin static, attestation, and executor bypass: `117 passed`.

Log: `/opt/cursor/artifacts/foundation-hardening-pytest.txt`.

Python 3.11 is not installed in this environment (`python3.11` absent; apt cache had no `python3.11` candidate without a distro change). The full canonical 3.11 and 3.12 matrix was not executed here. Coverage thresholds were not lowered. Terraform 1.9.8 `fmt -check` on `locals.tf` passed. Ruff check passed on the edited Python files.

This is not a green CI claim for the whole repository.

## I. Runtime, MCP, identity, delegation, policy, and tenant qualification

Hosted MCP still requires governance, an organization, and a purpose before execution. Enterprise stdio still refuses to start. Trust outage on a named provider/model now requires approval inside the gateway used by `apply_governance`. Delegation widening fixes already on the ancestry were not reverted. New policy writes cannot hide a stricter rule behind a broader weaker rule. Legitimate narrower delegation and the specific-allow-before-broad-deny pattern are preserved.

Tenant identity for authenticated dashboard limits comes from the resolved organization on `request.state`, not from a client-supplied org argument. The governed test-counter path still overwrites `_whitepact_organization_id` from the authorized action in `InternalToolExecutor`.

Not re-qualified end to end in this session: every REST route, every SSO provider against a live IdP, and multi-replica behavior on real PostgreSQL and Redis.

## J. Cloud, egress, isolation, cryptography, and audit evidence

Authority HTTPS egress is allowlist-only in the generated nftables output rules. Reproduction used `nft` inside a network namespace with a veth route, not `terraform apply` and not a live Hetzner host. Backup to an address that is actually in `authority_egress_cidrs` still matches accept. Operators must list R2 or update addresses there. Port 53 was already absent from this output chain; removing the catch-all does not add or remove DNS.

Residual: the SaaS output chain still accepts TCP 80 and 443 to any destination when NAT is enabled (image and update egress). The NAT gateway forward chain still masquerades private-to-public traffic. Host nftables on the authority tier is what now constrains that tier.

Evidence: database hash chain is an internal consistency check. Witness signatures are Ed25519 over a canonical head payload. The signing key is supplied by the caller and is not written by this module. No external anchor was published.

## K. Packaging and supply-chain qualification

No version bump. No publish. Workflow `uses:` lines with a floating `@vN` tag were not found in `.github` on this tree; pin enforcement from the ancestor commits remains. This pass did not rebuild wheels, SBOMs, or signatures.

## L. External dependencies and unexecuted live gates

- `LIVE_ANCHOR_STATUS = EXTERNAL_BLOCKER` in `responsibleai.governance.evidence_witness`. A live transparency log or locked object store was not provisioned and must not be treated as done.
- No live Hetzner, Cloudflare, or NAT gateway was contacted. The nft namespace shows the rule verdict, not a cloud deployment.
- Python 3.11 full matrix: not executable here.
- Full pytest with coverage: not run.
- Multi-replica on real Redis and PostgreSQL: not executed.
- Independent Antigravity retest: not done.

## M. Independent Antigravity audit handoff

Branch: `cursor/whitepact-foundation-hardening-934e`.

Base for the delta: `7a0852899afd997264c384a9ff5ca5f99a65c7ca` (`cursor/whitepact-phase3-preflight-b6a9`).

Please retest, at minimum:

1. Authority nftables output with NAT enabled contains no unrestricted `tcp dport 443 accept`, and a non-allowlisted destination is dropped while an allowlisted destination is accepted.
2. Gateway ALLOW becomes `REQUIRE_APPROVAL` with `TRUST_LOOKUP_UNAVAILABLE` when `trust_state.error` is set, and stays ALLOW for a successful `known=False` result.
3. A DENY covered by an earlier ALLOW cannot be inserted, reordered into that position, or stored as a policy revision. A specific ALLOW before a broader DENY still can.
4. Two bearer tokens with the same `audit_org_id` share a rate-limit key. Hosted MCP auth failures from one address do not reset when the token changes.
5. `verify_chain` is not described or treated as proof against a rewriting database administrator. `verify_evidence_head` rejects a different head. Live anchoring is still an external blocker.
6. Production `enforce_shared_backends_for_multi_replica` raises for sqlite/memory and does not raise for postgresql/redis. Non-production does not raise.
7. Memory-scope delegation denial and enterprise stdio refusal still hold on this branch.

Do not treat this report as the independent qualification.

## N. Residual risk register

- SaaS-tier NAT egress remains broad TCP 80/443 by current policy text. Not changed in this pass.
- NAT gateway forwarding still accepts private-to-public traffic. Authority hosts must keep their own output policy.
- Community stdio is ungoverned by design. Enterprise mode refuses it. A mis-set trust domain on a non-production host is still an operator error outside the hosted production preflight.
- Dashboard rate limits are organization-scoped only after `get_org_context` has set `audit_org_id`. Calls that never resolve an organization stay per token or per address.
- Process-local limits remain for non-production single-process runs. Production multi-replica without shared backends now refuses to start; a deployment that ignores that flag and runs multiple processes anyway is outside the enforced declaration.
- Unknown models from a successful Trust Index response do not require approval. That is deliberate and tested.
- Evidence witnesses are not published. A database rewrite remains invisible to `verify_chain` until an external witness exists and is checked.
- Direct Python imports of engines are not mediated.
- This review did not exhaust every route, worker, and migration. Absence of a finding in an unreviewed path is not evidence of safety.

## O. Final verdict

HARDENING IMPLEMENTED — INDEPENDENT REVIEW REQUIRED

Confirmed defects FH-01 through FH-07 are fixed or, for live evidence publication, explicitly marked `EXTERNAL_BLOCKER` rather than described as deployed. No merge, deploy, or publish was performed. Do not treat this branch as production-ready or as a launch candidate.
