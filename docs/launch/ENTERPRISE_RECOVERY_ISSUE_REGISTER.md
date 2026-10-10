# Enterprise recovery issue register

Current register for branch `cursor/whitepact-enterprise-recovery-eedb`.

This file does not replace earlier registers. `docs/launch/AUTHORITATIVE_ISSUE_REGISTER.md` remains the record of candidate `5fbd48b1af72b965e95f839191b8f19c6fa37f6e`. Historical files listed there stay on disk. No GitHub issue was closed by this register.

The qualifying commit and tree are `git rev-parse HEAD` and `git rev-parse HEAD^{tree}` on this branch at handoff. A SHA written into this file would be stale after the next commit, so the inclusion gate (`scripts/check_security_fix_inclusion.py`) checks the tree by control text and regression-test names.

## Inherited controls

PR #175 unified security work is an ancestor of this branch. PR #178 launch-gate fixes LG-01, LG-02, and LG-03 are ancestors. PR #176 commit `1b974d5` (fail-closed trust wording) is included as `4cda648`. PR #176 commit `1e75790` is not cherry-picked: tenant admission in this tree is stricter than "missing organization returns None", and it covers OIDC, SAML, and verifiable credentials plus directory binding.

## Findings

| ID | Severity | Status | Evidence |
| --- | --- | --- | --- |
| P0-01 | P0 | Engineering fixed. Antigravity has not retested this tree. | OIDC admission requires an existing active organization and a pre-provisioned issuer/subject binding. Claimed roles cannot raise the directory role. `src/responsibleai/auth/tenant_admission.py`. `tests/test_p0_tenant_admission.py`. |
| P0-02 | P0 | Engineering fixed. Antigravity has not retested this tree. | SAML ACS and session resolution admit before a session is trusted. Expired and revoked sessions are denied. `tests/test_saml_app_routes.py`. |
| P0-03 | P0 | Engineering fixed. Antigravity has not retested this tree. | Verifiable-credential context uses the same admission function. `tests/test_mcp_verified_principal.py`. |
| P1-04 | P1 | Engineering fixed. Antigravity has not retested this tree. | Principal rows are written only after admission, with the admitted organization id. A failed audit write does not issue a session. |
| P1-05 / LG-04 | P1 | **Regressed by its own fix; see REC-01.** The runner was moved out of the caller workspace, but written 0o400, so every container run failed on Linux. Fixed in 19029d7. | Caller `workspace_files` cannot select the container entrypoint. The trusted runner is mounted read-only at `/opt/whitepact/runner.py`. Direct backend tests do not start a container. Docker daemon was not available in this environment, so live cgroup probes were skipped. `tests/test_runner_immutability.py`. |
| LG-01 | P1 | Inherited engineering fix. Independent retest still required. | `6b9115f`. `tests/test_launch_gate_isolation_runner.py` passed locally on this tree. |
| LG-02 | P1 | Inherited engineering fix. Independent retest still required. | `87e762c`. `tests/test_launch_gate_hosted_metering.py` passed locally on this tree. |
| LG-03 | P1 | Inherited engineering fix. Independent retest still required. | `c535770`. `tests/test_launch_gate_resume_identity.py` passed locally on this tree. |
| FH-01 .. FH-07 | Inherited | Local regression re-run. Not an independent qualification. Live evidence anchoring remains blocked. | `tests/test_foundation_hardening.py` passed in the local regression batch. Offline Ed25519 witness is not live external anchoring. The in-memory rate limiter is not a verified distributed limiter. |
| FH-06-LIVE | P2 | Blocked. | Live evidence anchoring is not deployed. |
| CLOUD-STAGING | Blocker | Blocked. | Owner approval `APPROVE STAGING CLOUD PROVISIONING` is not granted. Terraform validate ran for the Hetzner foundation module and the Cloudflare edge module. No apply, DNS change, or paid resource was created. |
| DOCKER-DAEMON | P2 | Superseded by REC-01: real containers were exercised on a Linux kernel in this pass. The earlier note that unit tests mock the runtime was the reason REC-01 went unseen. | `docker info` failed in this environment. Unit tests mock the container runtime. |

## Local automated evidence on this tree

These runs are engineering evidence. They are not Antigravity qualification and they are not a production capacity proof.

- Tenant admission, runner immutability, inclusion gate, MCP OAuth, verified principal, SAML routes, A2A trust: 73 passed.
- Foundation hardening, launch-gate, coverage-batch, and isolation unit tests: 327 passed, 3 skipped.
- PostgreSQL customer journey `tests/test_v1_customer_journey.py`: 10 passed.
- Governed effect `tests/test_v1_exactly_one_effect.py`: 1 passed.
- Two HTTP replicas sharing PostgreSQL, including bound OIDC and SAML: 1 passed after the directory status fix.
- `mypy` on the eight touched modules: no issues.
- `scripts/check_security_fix_inclusion.py`: passed for P0-01, P0-02, P0-03, P1-04, P1-05, and the PR #176 trust wording.
- Terraform `validate` succeeded for `infra/terraform/modules/whitepact-hetzner-foundation` and `infra/terraform/modules/cloudflare-edge`. `terraform fmt -check -recursive` exited 0. No apply.

## Open counts

Confirmed open P0 in the paths changed here: 0, pending independent retest.

Open P1 pending independent retest: P0-01, P0-02, P0-03, P1-04, P1-05, LG-01, LG-02, LG-03. Engineering status is fixed. They are not closed.

Open external blockers: FH-06-LIVE, CLOUD-STAGING, live container daemon, external enterprise identity providers, Antigravity re-qualification of this tree.

## Findings from the master-directive pass (branch `local/wave1-2-fixes`, not pushed)

Baseline: `3b61db0` (qualification-3fc1), the newest tip. `0f24e3f` is no longer the head.
Every row names the commit that fixes it and the evidence that was actually run. "Mutation-checked"
means the new test was shown to fail against the old code.

| ID | Sev | Status | What was wrong | Evidence |
| --- | --- | --- | --- | --- |
| REC-01 | P1 | Fixed `19029d7`. CI re-run pending (not pushed). | Linux CI on `0f24e3f` failed 27 real-container tests per job (3.11 and 3.12): `python3: can't open file '/opt/whitepact/runner.py': [Errno 13] Permission denied`. The runner was 0o400 and bind-mounted; on Linux the container UID 65534 could not read it, so **every isolated execution failed**. macOS Docker Desktop ignores host permissions, so local runs never showed it. | CI run 37975468376. Reproduced on a Linux 6.12 kernel (10 of 13 failed). After the fix: 38 passed as root; 53 passed, 1 skipped as uid 1001 with POSIX ACLs. Portable regression `test_trusted_runner_is_container_readable_but_never_writable` (mutation-checked). Reproduce with `scripts/verify-linux-container-isolation.sh`. |
| REC-02 | P1 | Fixed `58c40b7`. | Isolation was opt-in. `InternalToolExecutor` built an `IsolationBroker` only if `ENVIRONMENT=production` or `WHITEPACT_ISOLATION_BACKEND` was set, else ran `dispatch_tool` in-process; the broker also degraded silently from Docker to an uncontained subprocess outside "production". A deployment that omitted the variables ran governed tools with the host network and filesystem, bypassing isolation and controlled egress. Config-dependent, not attacker-triggerable. | `tests/test_isolation_fail_closed_default.py` (24; 5 fail on the old code, including "tool ran in-process on an unset environment"). One rule in `isolation/mode.py`; production ignores the opt-in. |
| REC-03 | P1 | Fixed `183e3d1`. | Grok's README finding was wider than one snippet: the quickstart crashed (`ActionRequest(tool_name=...)`), and four more examples called APIs that do not exist (`export_html`, `pii_count`, `run_all`) or printed nothing. | `tests/test_readme_examples.py` runs every offline block verbatim and requires each block to be classified. Fails 7 tests against the old README. |
| REC-04 | P1 | Fixed `993023f`. | `ComplianceEngine` matched keyword phrases by substring, so the documented `credit_scoring` classified as **MINIMAL** at 100%. `hiring` was missing. Normalising only the input would have downgraded the prohibited `real-time biometric surveillance` to HIGH; an existing test caught that. | 17 new tests including the prohibited-use case. Unknown use cases still default to MINIMAL (open limitation). |
| REC-05 | P1 | Fixed `a8f9cf6`. | `DeepfakeDetector` scored random noise when torch was absent (ignoring the file), ran untrained `weights=None` networks otherwise, returned random video scores, and reported an unreadable video as authentic. Scores flowed into the trust-score authenticity dimension. | Detector is experimental: needs `allow_experimental=True`, every result carries `validated=False`, `VALIDATED_DETECTORS` is empty, undecodable media raises. No accuracy is claimed. |
| REC-06 | P2 | Fixed `e777169`. | The inclusion gate matched text, so a control could survive in a comment and a regression "test" could be empty or skipped. The P1-04 control was "present" only because of a comment. | Gate now strips comments, requires a real assertion and no skip, and requires the behavioural gate to run each test. 13 tests on the gate itself. |
| REC-07 | P2 | Fixed `d32e253`. | `nltk.download()` ran inside scoring; it returns False when blocked, so scoring then crashed with `LookupError` offline. | No download; returns "no signal" with one warning; setup-time step documented. Fake-nltk tests (4 fail on old code). |
| REC-08 | P2 | Fixed `c6d7a6d`. | Docs described hallucination detection as estimating "factual reliability". It is TF-IDF, hedging regexes and claim-shaped regexes. | Docstring, README and MCP tool description now state what it does not do. |
| REC-09 | P2 | Fixed `a7652c2`, `1a47b9d`, `aba0b3c`. | DEF-01 was only partly closed. The audited tree failed 40 tests on macOS: 32 real-container tests (incl. one that silently *passed* when Docker was absent) plus 8 others. | Real-container tests record `QUALIFICATION_SKIP` off Linux and fail on Linux; CI sets `WHITEPACT_REQUIRE_DOCKER_ISOLATION=1`. Mocked unit tests stub only the host UID mapping. |
| REC-10 | P3 | Open. | Running the suite executes `terraform init`, which appends a host-specific provider hash to five tracked `.terraform.lock.hcl` files and creates a sixth, dirtying the working tree. Reverted by hand here. | Observed after the full run on macOS arm64. Fix: run Terraform tests in a temporary copy, or commit hashes for every supported platform with `terraform providers lock`. |

Already closed on this tree, re-verified: DEF-02 (platform-aware `nft`/`ip` tests) and DEF-03 (the 48 ruff findings
came from running over `scripts/`, which `pyproject.toml` excludes; the CI scope `src/ tests/ sdk/python/` is clean).

## Results of this pass

| Check | Result |
| --- | --- |
| Full suite, audited tree `3b61db0`, macOS arm64 | 40 failed, 5959 passed, 9 skipped (30 min) |
| Full suite, `c6d7a6d`, macOS arm64, PostgreSQL 16 | **6039 passed, 0 failed, 0 errors, 44 skipped** (17.6 min) |
| Real PostgreSQL 16 (migrations, auth, concurrency, nonce race) | 51 passed, 0 skipped |
| Real Linux containers, root | 38 passed |
| Real Linux containers, uid 1001 + POSIX ACLs | 53 passed, 1 skipped (the no-ACL path, which ran on macOS) |
| Live Redis shared rate limit | 2 passed (one machine, one Redis; not multi-host) |
| `ruff check`, `ruff format --check`, `mypy src/` | clean (412 files) |
| Inclusion gate, behavioural gate (18 nodes, skips fail), doc consistency | pass |

The 44 skips are the macOS-only `QUALIFICATION_SKIP`s plus the three README examples that need keys or user code. A skip is not a pass.

## Grok findings, current classification

| Grok finding | Status |
| --- | --- |
| Broken README example | CONFIRMED, fixed (REC-03) |
| Deepfake placeholder | CONFIRMED, fixed (REC-05) |
| Hallucination is heuristic | CONFIRMED, documentation corrected (REC-08) |
| Trust score is self-reported | PARTIAL. README, MCP resource and parameter docs now say so. A separate API/SDK/UI vocabulary is not done. |
| Conflicting product names | NO LONGER APPLICABLE as stated. On a clean install `whitepact`, `import whitepact`, the legacy aliases and version 1.3.1 all work and `docs/PACKAGE_IDENTITY.md` documents it. A PyPI distribution rename needs an owner decision. |
| Missing PostgreSQL / Docker / ACL / NLTK | FIXED (compose file, Linux verification script, REC-07, REC-09) |
| Flaky auth tests that fail only in the full suite | NOT REPRODUCED. No authentication test failed in the baseline or the post-fix run on this tree. |
| 89 failures / 145 setup errors | NOT REPRODUCED on this tree (0 errors; the failures were the macOS container class above). |
| Excessive root documentation | CONFIRMED (about 60 report files at the repo root). **Not done.** |

## Not done in this pass

- **HTTP and PostgreSQL authorization SLO.** Only the in-process kernel microbenchmark was refreshed (allow p50 0.0032 ms, p95 0.0034 ms, p99 0.0036 ms on an Apple M4, one core, no database, `c6d7a6d`). It is not an SLO. `scripts/load_test_dashboard.py` targets public pages of a hosted deployment, not authorization, so there is no honest p50/p95/p99 for the authenticated, database-backed path yet.
- Repository root clean-up; separate API/SDK/UI vocabulary for self-reported versus verified trust.
- Real browser onboarding journeys, external IdP interoperability, a real backup-and-restore drill, multi-replica and multi-host proof.
- FH-06-LIVE witnessing, cloud staging, penetration testing, legal and procurement items (external).
- Python 3.12 full run, CodeQL, bandit and dependency audit on this branch (CI-only; nothing was pushed).
- Antigravity independent re-qualification. Nothing here is independently verified.
