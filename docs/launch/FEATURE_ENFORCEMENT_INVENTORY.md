# Feature and enforcement inventory

Baseline: branch `claude/whitepact-isolation-failclosed-linux-recovery` (PR #180). Re-read the PR for the exact head;
this file is edited together with the code it describes. Counts were produced by code on 2026-10-10:
**30 advertised MCP tools (31 definitions; the 31st, `test.counter.increment`, is a test fixture that is never listed), 20 MCP resources, about 280 HTTP routes in the dashboard app**, 372 Python modules (83k lines) in
`src/responsibleai`, 391 files under `tests/`.

Status words: **Engineered + tested** (implemented, covered by tests I ran or CI ran; no independent qualification of
*this* SHA), **Partial**, **Experimental**, **Planned**, **Unsupported**, **Not reviewed** (exists, I did not examine it
in this pass; no claim). Nothing here is "Qualified": that word is reserved for Antigravity after exact-SHA review.

| Area | Source | Status | Evidence / limits |
| --- | --- | --- | --- |
| Python distribution `rai-governance-platform` 1.3.1, CLIs `whitepact`, `whitepact-mcp`, `whitepact-mcp-http`, legacy `responsibleai*`, `biasbuster` | `pyproject.toml`, `src/whitepact/`, `src/responsibleai/` | Engineered + tested | Classifier changed from `5 - Production/Stable` to `4 - Beta` (this pass); wheel smoke 3.11/3.12 in CI |
| Governance kernel (decision, gateway, risk, authority) | `governance/gateway.py`, `models.py`, `risk.py`, `authority*` | Engineered + tested | `tests/test_executor_bypass_invariant.py`, `test_authority_grant.py`, many |
| Policy rules, first-match, shadowed-restrictive-rule rejection | `governance/policy.py`, `db/policy_repository.py` | Engineered + tested | `test_policy_*` |
| Policy change history, tamper-evident, counter cross-check | `db/policy_repository.py`, migration `0062` | Engineered + tested | `tests/test_policy_history.py`, `test_policy_history_migration.py`; no external anchor |
| Policy lifecycle (revisions, activation, rollback, step-up, four-eyes) | `governance/policy_lifecycle.py` | **Partial: not wired to any route** | Register REC-25; founder decision pending |
| Identity, delegation, ceilings, revocation epoch | `iam/`, `enterprise/`, `db/revocation_epoch_repository.py` | Engineered + tested | `test_iam_adversarial_matrix.py`, `test_mcp_ws2_authority_matrix.py` |
| Approvals (quorum, resume, replay) | `governance/approval.py`, web/REST routes | Engineered + tested | `test_v1_exactly_one_effect.py`, `test_transport_credential_negatives.py` |
| Execution authorization, single-use nonce | `governance/execution.py`, `db/execution_nonce_repository.py` | Engineered + tested | `test_executor_bypass_invariant.py`; cross-process replay NOT TESTED |
| Hosted MCP Streamable HTTP | `mcp/server.py`, `mcp/governance_integration.py` | Engineered + tested | `test_mcp_governance_dispatch.py`, `test_mcp_http_credential_negatives.py`; spec 2026-07-28 conformance NOT TESTED |
| Legacy HTTP/SSE MCP | `mcp/` | Not reviewed | |
| Community stdio MCP | `mcp/server.py main` | **Ungoverned by design** | `docs/launch/LOCAL_STDIO_MCP_SCOPE.md` |
| REST governed tool call | `dashboard/app.py /api/v1/governance/tools/call` | Engineered + tested | Customer journey CI job |
| Upstream MCP proxy | `mcp/` upstream | Engineered + tested | `test_mcp_ws2_upstream_reconciliation.py` |
| Container isolation (Docker, no network, ro root, UID 65534) | `isolation/container_backend.py`, `Dockerfile.isolation` | Engineered + tested on Linux | Real-container tests required in CI; macOS records QUALIFICATION_SKIP (not a pass) |
| Subprocess backend (no containment) | `isolation/subprocess_backend.py` | Local development only | Refused in production by `environment.py` |
| Controlled egress | `net/`, `infra/` nftables | Partial | Local namespace test only |
| Production detection | `environment.py` | Engineered + tested | `test_production_environment_resolution.py` |
| Host-side fixture `test.counter.increment` | `governance/synthetic_counter.py`, `isolation/mode.py` | Narrow exception, **not independently reviewed** | REC-12 |
| Evidence repository, hash chain | `db/evidence_repository.py` | Engineered + tested | concurrency (60 parallel), restore drill |
| Evidence witness / publication | `governance/evidence_publication.py` | Partial | File log only; no live anchoring (`live_object_store_status`) |
| Evidence bundle / attestation | `governance/evidence_bundle.py`, `attestation.py` | Engineered, **unsigned attestations** | `cryptographically_signed: false` |
| Dashboard SPA (React) | `web/src/features/*` | Partial | api-keys, auth, dashboard, onboarding, policy (add/remove/reorder), sovereign; no policy test/simulate, revision or history view |
| Legacy governance shell | `dashboard/legacy_templates/` | Retired in unified/production; served in community mode | XSS/redirect fixed this pass |
| Authentication, OIDC, SAML, SCIM, MFA | `auth/`, `iam/`, `dashboard/` | Engineered + tested | Real external IdP NOT TESTED |
| API keys | `db/org_repository.py` | Engineered + tested | revoke/expire immediate; `last_used_at` throttled to 60 s |
| Billing (Paddle/Stripe), metering, plan limits | `billing/`, `dashboard/plan_rate_limiter.py` | Partial | Sandbox only; no live payment evidence |
| Redis rate limit + capacity reservation | `runtime/capacity_reservation.py` | Engineered + tested | live Redis, 3 clients; failover NOT TESTED |
| PostgreSQL schema, 62 migrations (head `0062`) | `migrations/` | Engineered + tested | rollback feasibility NOT TESTED |
| Backup / restore scripts | `scripts/backup-postgres.sh`, `restore-postgres.sh` | Engineered + tested (local) | not a DR qualification |
| Observability (Prometheus, OTel, structured logs) | `dashboard/`, `ops/` | Not reviewed this pass | |
| Terraform (Hetzner, Cloudflare, optional GCP) | `infra/terraform/` | Prepared, never applied | no live apply authorised |
| Python SDK | `sdk/python/rai_client/` | Partial | server-side enforcement via `call_tool`; boundary now documented |
| TypeScript SDK | `sdk/typescript/` | Not reviewed this pass | |
| Go SDK | `sdk/go/raiclient/` | Not reviewed this pass | |
| Agent-framework integrations | `integrations/` | Not reviewed this pass | each advertised one needs a clean-env smoke test |
| Trust scoring, bias, hallucination, guardrails, red team, compliance | `trust/`, `biasbuster/`, `hallucination/`, `guardrails/`, `redteam/`, `compliance/` | Experimental / heuristic | `docs/EXPERIMENTAL_MODULES.md`; nothing rated STABLE |
| Deepfake detection | `privacylabel/deepfake/` | **Experimental, `validated=False`** | no accuracy claim |
| Sovereign (authority shadow/simulation) | `sovereign/` | Not reviewed this pass | non-authoritative analytics |
| FastStart | PR #183 (not in this branch) | Under Antigravity remediation | `docs/launch/PR183_FASTSTART_REVIEW.md` |
| CI/CD, supply chain | `.github/workflows/` | Engineered | exact-SHA CI required; SBOM / signed provenance NOT VERIFIED here |

Enforcement paths are in `docs/launch/ENFORCEMENT_PATH_MATRIX.md`.
