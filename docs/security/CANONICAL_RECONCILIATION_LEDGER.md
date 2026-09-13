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

---

## Entry 3 — Wave 2: Phase 2 Runtime Isolation

| Field | Value |
|---|---|
| Source branch | `feature/runtime-isolation-phase2` |
| Source SHA | `3784b19619d8a3eb0b6a22150f06e540e0e2df7a` |
| Source commits | 5: `50d74ac` (isolation plane implementation), `5ea10e5` (closure doc), `3e942ee` (adversarial/stress/admission tests + broker/container_backend hardening), `5bf965f` (narrow, commit-anchored `.gitleaksignore` entry for a synthetic-secret false positive in `tests/test_ops_secret_redaction.py`), `3784b19` (empirical hard-gate evidence suite) |
| Security invariant | Untrusted execution never runs same-process; there is no production subprocess fallback; a sandbox cannot start without a valid `ExecutionAuthorization`; missing/unavailable isolation backend never falls through to direct execution; isolated execution is contained against host HOME/repo/external-canary/cross-tenant-workspace/path-traversal/symlink-escape access and against Docker-socket/containerd-socket/Kubernetes/SSH-agent/cloud-credential leakage. |
| Canonical implementation location | `src/responsibleai/isolation/` (new package: `broker.py` admission gate, `container_backend.py`, `subprocess_backend.py`, `environment.py`, `filesystem.py`, `models.py`, `errors.py`), wired into `src/responsibleai/governance/execution.py` |
| Classification (per behavior, before integrating) | `50d74ac`/`3e942ee` (isolation plane + hardening): net-new, no existing `isolation/` module in candidate to conflict with or supersede — **SAFE_SELECTIVE_CHERRY_PICK**, executed as a real `git merge` since a `git merge-tree` dry run confirmed zero textual conflicts and candidate had not touched `governance/execution.py` since the merge-base (`93c8e88`). `5ea10e5`/`3784b19` (docs/tests): **SUPPORTING_TEST_OR_DOC**. `5bf965f` (gitleaks suppression): read in full — narrow, commit-fingerprint-anchored, explanatory comment, for a synthetic test value in a negative secret-redaction test — accepted as legitimate repository hygiene, not a broad suppression. |
| Integration method | Real `git merge` (merge commit `dca1ac0`, amended once for the missing DCO sign-off, still unpushed at that point). |
| Tests | `test_runtime_isolation_admission.py`, `test_runtime_isolation_security.py`, `test_runtime_isolation_resources.py`, `test_runtime_isolation_stress.py`, `test_runtime_isolation_hardgate.py`, `test_runtime_isolation_docker.py` |
| Verification performed this pass | Phase 2 dedicated suite: **40 passed, 1 benign pytest-marker warning, 0 failed**. `test_runtime_isolation_docker.py`'s 7 tests are gated by `pytest.mark.skipif(not _docker_available(), ...)` — **independently confirmed Docker is actually available in this environment** (`docker info` succeeds) and all 7 ran as real empirical container tests, not mocked/skipped: container configuration proof, environment-secret containment, filesystem-canary containment, socket containment, network containment, timeout/process cleanup, concurrent-execution no-cross-tenant-collision — all **PASSED** for real. Checked for lingering containers after the run (`docker ps -a` sorted by creation time): the most recently created container predates this session by 3 days and belongs to a different, unrelated lane (`whitepact-wave3-redis`/`-pg`) — **zero lingering containers from this pass's own test run**. Regression: Checkpoint 6 + DNS/egress + tenant-isolation + MCP/upstream/webhook suites re-run fresh, **283 passed, 0 failed** (0 Checkpoint-6 regressions, 0 DNS regressions). ExecutionAuthorization/evidence: `test_executor_bypass_invariant.py`, `test_phase1_execution.py`, `test_phase1_release_gate.py`, `test_phase1_live_admission.py`, `test_checkpoint5_evidence_integrity.py`, `test_evidence_bundle.py`, `test_jit_credential.py` — **91 passed, 1 skipped, 0 failed**. `ruff`/`mypy`/`git diff --check`/SPDX scoped to every merged file: clean. No migrations touched (`git diff ... -- migrations/` empty). |
| Canonical commit SHA (this pass) | `dca1ac0` (merge, DCO-amended) |
| Status | **CLOSED**. P0: 0. P1: 0. Same-process untrusted production execution: 0. Production direct fallback: 0. Unauthorized sandbox starts: 0 (per `test_runtime_isolation_admission.py`). Sandbox escape successes: 0 (per the empirical Docker adversarial suite). Lingering containers/descendants: 0. |
| Deferred | `WP-ISO-01` (P2, hard workspace/disk quota incomplete) — carried forward, not reopened; belongs to later production/SRE hardening per the governing mission's own instruction. |

---

## Entry 4 — Wave 3: Phase 3 Global Trust Fabric

| Field | Value |
|---|---|
| Source branch | `feature/global-trust-fabric-phase3` |
| Source SHA | `53704a12269aea6eb467241a016c163d1e13e7df` |
| Source commits | 2: `044b135` (initial implementation: Principal Directory, bootstrap, passport, authority graph, challenge, conflict, decision, federation, monitor, proofs, provenance + migration `0043`), `53704a1` (final enterprise closure: hardening, provider.py, benchmark script, expanded adversarial/challenge/monitor/provider test suites) |
| **Structural finding, discovered this wave**: Phase 3 → Phase 4 → Phase 5 are **not independent sibling branches** — each is a direct git ancestor of the next (`git merge-base --is-ancestor` confirmed both links). Phase 4's branch already contains every Phase 3 commit; Phase 5's branch already contains every Phase 3 and Phase 4 commit. This does not change the integration order (still one wave at a time, each independently verified and ledgered) but explains why Waves 4 and 5's own "unique commits" diffs will be small. |
| Security invariant | WhitePact enforces organizational authority without silently becoming the organization's root authority. Bootstrap is single-winner under concurrent contention; a consumed bootstrap token cannot be replayed; cross-tenant bootstrap is rejected; a deleted/recreated organization or reassigned domain cannot resurrect prior authority; a tampered or key-mismatched Trust Passport is rejected; a consumed challenge cannot be replayed; conflicting trust claims are isolated per-tenant. |
| Canonical implementation location | `src/responsibleai/trust_fabric/` (new package: `directory.py`, `bootstrap.py`, `passport.py`, `authority_graph.py`, `challenge.py`, `conflict.py`, `decision.py`, `federation.py`, `monitor.py`, `proofs.py`, `provenance.py`, `provider.py`, `enums.py`, `errors.py`, `models.py`), `src/responsibleai/db/engine.py` (new trust_fabric tables), migration `migrations/versions/0043_global_trust_fabric.py` |
| Classification | Net-new package and migration, no existing `trust_fabric/` module in candidate, candidate had not touched `db/engine.py` since the merge-base — **SAFE_SELECTIVE_CHERRY_PICK**, executed as a real `git merge` (zero conflicts confirmed via `git merge-tree` dry run first). |
| Integration method | Real `git merge` (merge commit `1961528`, amended for DCO sign-off, still unpushed at that point). |
| Migration | `0043_global_trust_fabric.py` — sequential after candidate's own head (`0042`), no numbering collision. **Cross-checked against Phase 4/5's own branch contents**: Phase 4 adds `0044`, Phase 5 adds `0045` — both sequential, no collision risk for the upcoming waves either. Verified `alembic heads` reports a single head at every step. |
| Tests | Ran with a real local PostgreSQL 17 (Homebrew) database (`wp_phase3_test`, created fresh via `createdb`/`dropdb` after a schema-lineage safety check correctly refused to migrate a stale unversioned copy of that database left over from earlier authoring) — `tests/test_phase3_postgres_concurrency.py`, `test_principal_directory.py`, `test_trust_bootstrap.py`, `test_trust_conflicts.py`, `test_trust_decision.py`, `test_trust_federation.py`, `test_trust_passport.py`, `test_trust_privacy.py`, `test_trust_proofs.py`, `test_trust_challenge.py`, `test_trust_monitor.py`, `test_trust_provider.py`, `test_entity_adversarial.py`, `test_tenant_privacy_matrix.py`, `test_postgres_migrations.py` |
| Verification performed this pass | **88 passed, 0 failed.** Real PostgreSQL concurrency: confirmed `test_phase3_postgres_concurrency.py` runs **50 concurrent bootstrap attempts** via `asyncio.gather` (matches the mission's own 25–50-attempt guidance) and asserts single-winner semantics — passed. Confirmed by test name that the mission's named attack classes are covered: `test_bootstrap_replay_attack_rejected`, `test_cross_tenant_bootstrap_rejected`, `test_concurrent_bootstrap_race_single_winner`, `test_domain_transfer_and_org_recreation_no_authority_resurrection`, `test_conflict_cross_tenant_isolation`, `test_passport_tampering_and_key_mismatch`, `test_challenge_replay_prevented`. **Not separately confirmed by an explicitly-named test**: "algorithm confusion" and "unknown issuer" specifically — recorded honestly rather than assumed covered by the general passport/challenge suites. `test_postgres_migrations.py::test_one_canonical_alembic_head` independently confirms a single Alembic head. Regression: `test_checkpoint6_transport_boundary.py`, `test_dns_egress_security.py`, `test_runtime_isolation_admission.py`, `test_runtime_isolation_security.py`, `test_executor_bypass_invariant.py`, `test_phase1_execution.py`, `test_checkpoint5_evidence_integrity.py`, `test_tenant_isolation.py`, `test_mcp_governance_dispatch.py` — **200 passed, 1 skipped, 0 failed** (0 regressions across Waves 0–2). `ruff`/`mypy`/`git diff --check`/SPDX on every merged file: clean. Test database dropped after verification, no residual state left. |
| Canonical commit SHA (this pass) | `1961528` (merge, DCO-amended) |
| Status | **CLOSED.** P0: 0. P1: 0. Root bootstrap winners: 1 (single-winner, verified under real 50-way concurrency). Customer-root backdoors: 0. Cross-tenant trust effects: 0. Authority resurrection: 0. |

---

## Entry 5 — Wave 4: Phase 4 Enterprise IAM

| Field | Value |
|---|---|
| Source branch | `feature/enterprise-iam-phase4` |
| Source SHA | `8c7534975d63ee7b752f96d974baf2239b31573b` |
| Source commits | 2 unique vs. Phase 3 (confirmed direct descendant, per Entry 4's structural finding): `ada15ef` (initial implementation), `8c75349` (fix: link Checkpoint-5 canonical evidence, bound break-glass capabilities, enforce recovery separation) |
| Security invariant | Privileged administration is tenant-bound and durably attributed; critical actions require step-up/four-eyes and cannot be self-approved; break-glass access is incident-bound, TTL-capped, and cannot become permanent ownership or a policy/evidence/customer-root bypass; root recovery uses an N-of-M guardian ceremony and cannot be forged; a platform operator cannot backdoor into customer-root authority. |
| Canonical implementation location | `src/responsibleai/iam/` (new package: `guard.py` `PrivilegedSurfaceGuard`, `attribution.py`, `step_up.py`, `session.py`, `api_key.py`, `scim.py`, `jit.py`, `four_eyes.py`, `break_glass.py`, `recovery.py`, `transfer.py`, `enums.py`, `errors.py`, `models.py`), `src/responsibleai/db/engine.py` (new IAM tables), migration `0044_enterprise_iam_privileged_admin.py` |
| Classification | Net-new package, no existing `iam/` module in candidate, no `db/engine.py` divergence since the Wave 3 merge — **SAFE_SELECTIVE_CHERRY_PICK**, executed as a real `git merge` (zero conflicts, verified via `git merge-tree` dry run). |
| Integration method | Real `git merge` (merge commit `f037b76`, amended for DCO sign-off, still unpushed at that point). |
| Migration | `0044_enterprise_iam_privileged_admin.py` — sequential after `0043` (Wave 3), no collision, as already cross-checked in the Wave 3 entry. `alembic heads` confirms a single head at `0044`. |
| Tests | `test_phase4_migrations.py` (real PostgreSQL, self-managed test databases via `PG_ADMIN_URL`/`PG_BASE_URL`), `test_iam_adversarial_matrix.py`, `test_governance_and_sovereign_recovery.py`, `test_privileged_surface_guard.py`, `test_scim_and_session_lifecycle.py`, `test_step_up_authentication.py` (in-memory SQLite for the latter five) |
| Verification performed this pass | **39 passed, 0 failed.** Confirmed by test name every attack the mission explicitly names for this phase: `test_platform_operator_backdoor_blocked`, `test_vector_operator_backdoor_blocked`, `test_cross_tenant_escalation_blocked`, `test_vector_cross_tenant_impersonation`, `test_vector_jit_self_approval_blocked`, `test_four_eyes_dual_custody_self_approval_blocked` / `test_vector_four_eyes_self_approval_blocked`, `test_break_glass_requires_incident_and_capped_ttl` / `test_break_glass_ttl_bounds_rejection` / `test_vector_break_glass_invalid_incident_or_ttl`, `test_sovereign_root_recovery_n_of_m_ceremony` / `test_vector_sovereign_recovery_forged_guardian_signature`, `test_voluntary_root_transfer_lifecycle` / `test_vector_break_glass_root_transfer_and_capability_mismatch` — all passed. `test_phase4_migrations.py::test_one_canonical_alembic_head` confirms a single head. Regression across Checkpoint 6 + DNS + Phase 2 isolation + Phase 3 trust bootstrap/passport + execution/evidence + tenant isolation: **167 passed, 0 failed** (0 regressions across Waves 0–3). `ruff`/`mypy`/`git diff --check`/SPDX on every merged file: clean. |
| Canonical commit SHA (this pass) | `f037b76` (merge, DCO-amended) |
| Status | **CLOSED.** P0: 0. P1: 0. Privileged bypasses: 0. Cross-tenant admin: 0. Self-approved critical action: 0. Operator customer-root backdoor: 0. |
| Deferred to Wave 5 | Section 15's Phase 4 ↔ Phase 5 hard-boundary tests (critical policy mutation governed by canonical Phase-4 IAM) cannot be meaningfully exercised until Phase 5's own policy-mutation surfaces exist in the candidate — correctly sequenced to Wave 5's own verification, not skipped. |

---

## Entry 6 — Wave 5: Phase 5 Policy / Data Governance

| Field | Value |
|---|---|
| Source branch | `feature/policy-data-governance-phase5` |
| Source SHA | `9fa6f05fbcd67de4a3435736476f10d52ba05465` |
| Source commits | 3 unique vs. Phase 4 (direct descendant, per Entry 4's structural finding): `d1ca737` (initial: policy lifecycle, data governance package, migration `0045`), `00c62c5` (hardening + backup-resurrection closure), `9fa6f05` (durable Store-B provider + restore-admission chokepoint wired across webhooks/MCP/execution/IAM guard) |
| Security invariant | Policy revisions are immutable and digest-bound; activation is atomic with safe rollback; a stale policy version or a security-epoch change after approval invalidates a queued critical mutation; data export/retention/erasure/legal-hold decisions are tenant-scoped and cannot silently complete partially as if whole; a restored backup or a not-yet-admitted durable lifecycle store cannot resurrect prior authority or serve consequential requests. |
| Canonical implementation location | `src/responsibleai/data_governance/` (new package), `src/responsibleai/governance/policy_lifecycle.py` (new), `src/responsibleai/db/engine.py`/`org_repository.py`, migration `0045_policy_lifecycle_data_governance.py`, restore-admission chokepoint wired into `webhooks/manager.py`, `mcp/server.py`, `governance/execution.py`, `governance/upstream_executor.py`, `iam/guard.py` |
| **Real conflicts found and resolved by hand** (first wave where `git merge-tree` reported non-zero conflicts) | **1. `.gitleaksignore`**: both Wave 2 (Phase 2) and this branch independently added the *same* fingerprint (`06ac6cc1...:tests/test_ops_secret_redaction.py:generic-api-key:44`) with slightly different comment wording — resolved by keeping one copy, not a duplicate. **2. `src/responsibleai/webhooks/manager.py`** — a genuine, security-relevant conflict, not cosmetic: this branch's own `fire()` signature predates Checkpoint 6 (Wave 0) and lacks the `org_id` tenant-scoping parameter entirely; naively taking it would have **reintroduced the exact cross-tenant webhook delivery vulnerability Checkpoint 6 closed**. Resolved by keeping Checkpoint 6's tenant-scoped signature (`org_id` parameter, `config.org_id == org_id` filter) and inserting this branch's `assert_restore_readiness_admitted()` call at the top of the same method — both fixes now coexist, neither is dropped. **Verified no caller regression**: grepped every `.fire(` call site (5 total, all in `dashboard/app.py`/`db/approval_repository.py`, all pre-existing from Checkpoint 6, none added or touched by this branch) — confirmed this branch never introduced a new call site that would need updating for the `org_id` parameter. |
| Classification | Data-governance/policy-lifecycle package: net-new, **SAFE_SELECTIVE_CHERRY_PICK** via real merge. `webhooks/manager.py`'s restore-readiness check specifically: **CONFLICT_REQUIRES_PM_REVIEW** in spirit (a real security-relevant collision) but resolved directly per the mission's own instruction to preserve ONE canonical transport-admission architecture — Checkpoint 6's tenant-scoping is the stronger, newer canonical behavior and was preserved, not superseded. |
| Integration method | Real `git merge` with 2 hand-resolved conflicts (merge commit `6804dc5`, DCO sign-off present without needing amendment this time). |
| Migration | `0045_policy_lifecycle_data_governance.py` — sequential after `0044` (Wave 4), no collision, as already cross-checked in the Wave 3 entry. `alembic heads` confirms a single head at `0045`. |
| Tests | 19 Phase-5 dedicated test files (migrations via real PostgreSQL self-managed databases; the rest in-memory SQLite, including `test_phase5_postgres_concurrency.py` despite its name) |
| Verification performed this pass | **Phase 5 dedicated suite: 70 passed, 1 skipped, 0 failed.** **Section 15 (Phase 4↔5 hard boundary) explicitly confirmed by test name, all already passing**: `test_direct_critical_policy_mutation_fails_without_caller` (direct service bypass blocked), `test_missing_step_up_critical_mutation_blocked`, `test_fabricated_approval_id_blocked`, `test_expired_approval_blocked`, `test_already_consumed_approval_blocked` (replay), `test_cross_tenant_approval_blocked`, `test_self_approval_prevention_real_enforcement`, `test_approval_policy_digest_mismatch_blocked`, `test_security_epoch_changed_after_approval_blocked`, plus the positive case `test_fully_authorized_critical_policy_mutation_succeeds` — every scenario Section 15 names, covered. **Post-hand-resolution regression, specifically targeting the two merged fixes**: `test_checkpoint6_transport_boundary.py` + `test_tenant_isolation_webhooks.py` + `test_webhooks.py` + `test_webhook_persistence.py` (cross-tenant webhook fix intact) + `test_dns_egress_security.py` (SafeNetworkBackend intact) + `test_runtime_isolation_admission.py` + `test_trust_bootstrap.py` + `test_iam_adversarial_matrix.py` + `test_checkpoint5_evidence_integrity.py` + `test_tenant_isolation.py` + `test_mcp_governance_dispatch.py` — **289 passed, 0 failed** (0 regressions across Waves 0–4, and specifically confirms the hand-merged `webhooks/manager.py` preserves both fixes correctly). `ruff`/`mypy`/`git diff --check`/SPDX on every merged and hand-resolved file: clean. |
| Canonical commit SHA (this pass) | `6804dc5` (merge, hand-resolved, DCO present) |
| Status | **CLOSED.** P0: 0. P1: 0. History rewrites: 0. Stale policy execution: 0. False erasure completion: 0 (not independently re-attacked beyond the existing test suite's own coverage — recorded honestly, not claimed as freshly adversarially tested by this pass). Authority resurrection: 0. Old-backup resurrection: 0. |
