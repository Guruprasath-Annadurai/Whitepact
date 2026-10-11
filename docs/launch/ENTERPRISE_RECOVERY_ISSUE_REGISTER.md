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
| P1-05 / LG-04 | P1 | Engineering fixed. Antigravity has not retested this tree. | Caller `workspace_files` cannot select the container entrypoint. The trusted runner is mounted read-only at `/opt/whitepact/runner.py`. Direct backend tests do not start a container. Docker daemon was not available in this environment, so live cgroup probes were skipped. `tests/test_runner_immutability.py`. |
| LG-01 | P1 | Inherited engineering fix. Independent retest still required. | `6b9115f`. `tests/test_launch_gate_isolation_runner.py` passed locally on this tree. |
| LG-02 | P1 | Inherited engineering fix. Independent retest still required. | `87e762c`. `tests/test_launch_gate_hosted_metering.py` passed locally on this tree. |
| LG-03 | P1 | Inherited engineering fix. Independent retest still required. | `c535770`. `tests/test_launch_gate_resume_identity.py` passed locally on this tree. |
| FH-01 .. FH-07 | Inherited | Local regression re-run. Not an independent qualification. Live evidence anchoring remains blocked. | `tests/test_foundation_hardening.py` passed in the local regression batch. Offline Ed25519 witness is not live external anchoring. The in-memory rate limiter is not a verified distributed limiter. |
| FH-06-LIVE | P2 | Blocked. | Live evidence anchoring is not deployed. |
| CLOUD-STAGING | Blocker | Blocked. | Owner approval `APPROVE STAGING CLOUD PROVISIONING` is not granted. Terraform validate ran for the Hetzner foundation module and the Cloudflare edge module. No apply, DNS change, or paid resource was created. |
| DOCKER-DAEMON | P2 | Blocked for live container proof. | `docker info` failed in this environment. Unit tests mock the container runtime. |

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
