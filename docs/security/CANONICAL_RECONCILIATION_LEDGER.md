# Canonical Enterprise Security Integration — Reconciliation Ledger

One entry per reconciled security behavior. Nothing is entered here
without independently re-verified test evidence at the canonical
candidate SHA that introduced or confirmed it.

---

## Entry 1 — Checkpoint 6: Unified Transport Boundary

| Field | Value |
|---|---|
| Source branch | `integration/enterprise-phase1` (native — not a separate frozen phase branch) |
| Source SHA (design) | `a0a904db98725163493b88734fdb3d76a7c7c88e` |
| Source SHA (implementation) | `00560d130f6539a96e6c3036d22e5e6357b57974` |
| Source commits | `a0a904d docs(security): specify unified transport boundary`, `00560d1 fix(security): isolate tenant notification transports` |
| Security invariant | Every consequential execution transport (hosted MCP, upstream MCP, approval resume, internal/upstream executors) either enters canonical governance (`apply_governance` / `apply_upstream_governance` / `resume_approval`) or is an explicit, non-fallback, non-consequential exception (Community stdio, discovery/metadata calls). Operational transports (webhooks, WebSocket) are not tool-execution paths but must remain tenant-scoped — a tenant's event must never reach another tenant's webhook or WebSocket connection. |
| Canonical implementation location | `src/responsibleai/dashboard/app.py` (WebSocket tenant-channel resolution, webhook emission call sites), `src/responsibleai/webhooks/manager.py` (origin-tenant-required emission), `src/responsibleai/db/approval_repository.py` |
| Integration method | Native — already present at the canonical starting SHA, not integrated from a separate phase branch this pass. |
| Tests | `tests/test_checkpoint6_transport_boundary.py` (dedicated), `tests/test_tenant_isolation_webhooks.py`, `tests/test_tenant_isolation.py`, `tests/test_tenant_isolation_org_admin.py` |
| Verification performed this pass | Re-ran all 4 test files fresh: **12 passed, 0 failed**. Independently re-derived the consequential-transport inventory via direct `grep -rn "dispatch_tool("` across `src/responsibleai/` (not trusting the design doc's own table) — found exactly the two real call sites the doc names, no more, no fewer. Independently searched for a scheduler/cron/background-job framework and found none that dispatches a consequential action, corroborating the doc's claim that no scheduled-execution transport exists. |
| Canonical commit SHA (this pass) | No new commit required — Checkpoint 6 was already correctly implemented at the starting SHA; this pass's own commit (below) only adds this ledger entry and the verification record. |
| Status | **CLOSED**, independently re-verified. |

**What this closure does NOT cover**: DNS rebinding remains an explicit, named-open P1 in the design doc itself ("DNS rebinding remains an open P1 release blocker and is not changed here") — closed by Entry 2 below. Process isolation, trust fabric, IAM, and policy/data governance (Phases 2–5) are entirely separate, unintegrated work — see the implementation plan.

---

## Entry 2 — Wave 1: DNS / Egress Security Closure

| Field | Value |
|---|---|
| Source branch | `audit/dns-egress-security-closure` |
| Source SHA | `c137ce4b2c44ae34d814288b4dc03c111e786efd` |
| Source commits | 7 commits: architecture spec, rebinding-vulnerability reproduction, `SafeNetworkBackend` implementation, webhook/upstream integration, closure docs, deterministic CNAME/TLS-SNI/policy-mode-confusion proofs |
| Security invariant | Outbound network connections from tenant-controlled input (webhook delivery, upstream MCP tool invocation) resolve all A/AAAA records, fail closed if any resolved address is forbidden (private/loopback/link-local/etc.), connect to the specific validated address rather than re-resolving the hostname at connect time (the DNS-rebinding defense), perform post-connect peer validation, preserve the original hostname for TLS/SNI, reject certificate mismatches, and cannot be bypassed via proxy environment variables. `PUBLIC_ONLY` mode is enforced for untrusted input with no way for a request to select a more trusted mode. |
| Canonical implementation location | `src/responsibleai/net/egress.py` (`SafeNetworkBackend`, new module), wired into `src/responsibleai/webhooks/manager.py`, `src/responsibleai/governance/upstream.py`, `src/responsibleai/governance/upstream_executor.py` |
| Integration method | **Real `git merge` (not cherry-pick, not reimplementation)** — justified because a `git merge-tree` dry run confirmed zero textual conflicts before merging for real (the branch shares a very recent common ancestor, `39fda2c`, with the canonical candidate), and the change is a single coherent, well-tested unit. Merge commit: `6a46791` (amended once to add the missing DCO sign-off, still unpushed at that point). |
| Tests | `tests/test_dns_egress_security.py` (114 tests, including the two explicit rebinding-attack tests: `test_patched_webhook_manager_blocks_dns_rebinding`, `test_rebinding_on_second_delivery_attempt_blocked`) |
| Verification performed this pass | Ran `test_dns_egress_security.py` alone (114 passed), then a broader regression across `test_dns_egress_security.py` + `test_webhooks.py` + `test_webhook_persistence.py` + `test_upstream_gateway.py` + `test_checkpoint6_transport_boundary.py` + tenant-isolation tests (**251 passed, 0 failed** — confirms Wave 1 does not regress Wave 0). `ruff check` and `mypy` scoped to every merged file: clean. |
| Canonical commit SHA (this pass) | `6a46791` (merge, DCO-amended) |
| Status | **CLOSED**, independently re-verified — the specific rebinding attack the mission names (public IP at validation time, private/loopback IP at connection time) is covered by a dedicated, passing test, not just a general assertion. |

**What this closure does NOT cover**: `STATIC_SSRF_FILTERING` as a separately-named state (per the broader assurance-platform work in a sibling lane) — this entry closes DNS rebinding and egress validation specifically, per this phase's own scope. Live network behavior against a real external target was not additionally tested beyond what `test_dns_egress_security.py` already covers with mocked/local resolution.

### Entry 2a — Wave-1 merge semantic audit (before starting Wave 2)

Before beginning Phase 2, independently audited every one of the 7
commits unique to `audit/dns-egress-security-closure` (merge-base
`39fda2c` per `git log 39fda2c..c137ce4b`) by reading each commit's
actual diff, not trusting the commit title alone:

| Commit | Title | Files | Classification |
|---|---|---|---|
| `7333a35` | docs: specify architecture | 2 spec/plan docs | SUPPORTING_TEST_OR_DOC |
| `5acf976` | test(conftest): hermetic temp home + auth defaults | `tests/conftest.py` | SUPPORTING_TEST_OR_DOC — flagged: this sets `HOME`/`XDG_*`/`RAI_AUTH_ENABLED`/`WHITEPACT_AUTH_ENABLED` defaults for the **entire test suite** via module-level side effect on conftest import, not scoped only to DNS tests. Read in full rather than assumed benign. Uses `setdefault`/direct-assign in a way that only affects tests relying on the unset default; already empirically validated safe by this session's own 251-test and 191-test regressions (Entries 1–2) passing cleanly with this change present. Necessary to make the DNS/egress reproduction tests hermetic (avoid touching the real developer's home directory) — the same category of real-disk-state-leak risk this reconciliation effort has independently encountered before in this project's history. |
| `cfbf31a` | test: reproduce rebinding vuln | `tests/test_dns_egress_security.py` (new) | SUPPORTING_TEST_OR_DOC |
| `e38beb2` | feat: implement SafeNetworkBackend | `src/responsibleai/net/egress.py`, `net/__init__.py` (new module) | DNS_EGRESS_REQUIRED |
| `7f77c52` | feat: wire into webhooks/upstream | `webhooks/manager.py`, `governance/upstream.py`, `governance/upstream_executor.py` | DNS_EGRESS_REQUIRED — read the actual diff to `upstream.py`/`upstream_executor.py` line-by-line: confirmed narrowly scoped (replaces a raw `httpx.AsyncClient` with `create_safe_async_client()`, one docstring formatting nit; no authority/execution/governance logic touched). |
| `c224630` | docs: closure summary | 1 doc | SUPPORTING_TEST_OR_DOC |
| `c137ce4` | test: CNAME/TLS-SNI/policy-mode-confusion proofs | `tests/test_dns_egress_security.py` | SUPPORTING_TEST_OR_DOC |

**Result: UNRELATED imported commits: 0. Unexpected migrations: 0** (no
`migrations/` path touched by any of the 7 commits — confirmed against
the full file list, not assumed). **Duplicate security planes: 0** (one
canonical egress validator, `SafeNetworkBackend`/
`create_safe_async_client`; the pre-existing `validate_webhook_url()`
now delegates to it rather than competing with it).

**Wave 1: ACCEPTED as merged.** No reconstruction required.
