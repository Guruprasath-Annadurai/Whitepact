# Antigravity — independent audit of the entire supported WhitePact product

From Claude (Principal Engineering Lead). Scope set by the founder: audit the **whole supported product**, not only the latest
patch. You are an AI auditor; your findings do not replace a human reviewer or satisfy OSPS-QA-07.01. Production remains
**NO-GO**; nothing here authorizes a release, submission, DNS change, deployment or spend.

**Candidate.** PR #184 (`claude/whitepact-isolation-failclosed-linux-recovery-r2`), the DCO-clean successor of #180 (#180 is kept
untouched as history). Replay equivalence: #180 head `80d4bb71…` and the r2 commit `e32f9410…` have the **identical tree**
`ed5eb67d920d5ca71267e0c41f59e3c88a0ebdc6`. r2 has since moved; the exact head, tree and CI results are in the final engineering
report. Verify `git rev-parse HEAD^{tree}` against it before you start; anything else is a different candidate.
**Integration candidate for #183:** branch `integration/183-on-r2` (a merge, not a rewrite; your commits are preserved; see track H).

## How to work
Break things; do not confirm. For every claim in `docs/launch/ENTERPRISE_RECOVERY_ISSUE_REGISTER.md` (REC-01…REC-44) assume it is
wrong until a test you ran says otherwise. Report: what you ran, on which SHA, the result, and what you did **not** test. A skip
is not a pass. Do not weaken tests or scanners. Use disposable databases (`scripts/test-postgres.sh`, port 55433) and Linux
isolation via `scripts/verify-linux-container-isolation.sh [root|nonroot]`.

## Audit tracks
| # | Track | Entry points | Attack ideas |
|---|---|---|---|
| A | **Authority kernel and enforcement paths** | `docs/launch/ENFORCEMENT_PATH_MATRIX.md`, `FEATURE_ENFORCEMENT_INVENTORY.md`, `governance/`, `mcp/governance_integration.py`, `isolation/` | any route that executes without an `ExecutionAuthorization`; TOCTOU between grant and execute; revocation (in-flight tools are NOT cancelled — known); REC-12 host-side fixture exception (never independently reviewed) |
| B | **Identity, step-up, RBAC** | `iam/step_up.py`, `enterprise/`, `rbac/`, `dashboard/app.py` auth | forged/replayed TOTP, nonce age, CAS single-use; OIDC/WebAuthn must stay *refused*; legacy static keys in production; role matrix gaps; machine-credential scope |
| C | **Policy governance and history** | `governance/policy_change*.py`, `db/policy_repository.py`, migrations 0062/0063 | four-eyes bypass, digest binding, `expected_version`, baseline backfill, `verify_history` incl. the #183 parameters |
| D | **MCP hosted transport** | `mcp/server.py`, `auth/mcp_oauth.py`, `mcp/authority_tools.py`, `mcp/licensing.py` | OAuth redirect/PKCE/resource binding; the ChatGPT + Claude callback allow-list (REC-40); body limits; SSE vs Streamable HTTP; tool advertisement truthfulness; **the four authority tools (REC-35) — highest priority** |
| E | **Tenant isolation and data layer** | `db/*`, migrations, `tests/test_tenant_isolation*.py` | cross-org reads via every repository; Postgres-only behaviours; the authority read role (`AUTHORITY_READ_PATH.md`) |
| F | **Evidence and witness** | `governance/evidence*.py`, `evidence_publication.py` | chain tamper/rollback; witness v2 opaque reference (`WITNESS_DISCLOSURE_RECOMMENDATION.md` §7); object-lock anchor (`test_object_lock_anchor_live.py`) — **anchor is not provisioned** |
| G | **Availability, rate limits, capacity, billing** | `dashboard/plan_rate_limiter.py`, `ops/admission.py`, `db/billing_repository.py`, `db/paddle_billing_repository.py`, `docs/launch/CAPACITY_AND_DEGRADED_MODE.md` | plan-scaled route limits (REC-28), admission control (REC-41), Redis outage degradation (REC-38), webhook retry/concurrency/tenant isolation (REC-37), unknown-org events |
| H | **PR #183 FastStart integration** | `integration/183-on-r2` (merge `3ec1eb5a` on an older r2 head) | the reconciled `verify_history` signature; `src/whitepact/faststart.py` is unchanged and has one unused import that ruff flags; confirm FastStart claims against code; re-merge onto the final r2 head if you accept it |
| I | **Supply chain, CI, containers, SDKs** | `.github/workflows/*`, `Dockerfile*`, `sdk/{python,typescript,go}`, `docs/assurance/*` | pinned actions/digests; container scan gate (REC-39); Go SDK hardening (REC-43); SDK fail-open defaults; SBOM/provenance claims; the four DRAFT policies vs reality (`POLICY_ADOPTION_CHECKLIST.md`) |
| J | **Distribution claims** | `docs/distribution/*`, `server.json`, README | any statement implying production readiness, certification, third-party endorsement or demonstrated assistant compatibility (none exists); Smithery/Glama wording (`SMITHERY_GLAMA_LISTING_REVIEW.md`) |

## Known, not for you to "discover"
`docs/launch/STATUS_BY_CATEGORY.md` sections 4–7 (kept current). In short: CodeQL alerts 134/135 open and **not dismissed**;
no real assistant has connected; no staging/production endpoint; no provisioned witness anchor; no provisioned read-only DB
role; 1,000 concurrent clients **not** supported; OIDC/WebAuthn step-up unsupported; in-flight revocation not cancelled;
Stripe out-of-order events not handled; one maintainer (no independent human review).

## Reproduce
`uv sync` then `uv run pytest tests -q` (about an hour; Docker, Redis and Postgres tests need the daemon); Linux isolation:
`scripts/verify-linux-container-isolation.sh nonroot`; capacity: `scripts/bench_http_authorization.py --replicas N --max-inflight M`;
live-endpoint conformance (needs a staging endpoint that does not exist): `scripts/live_mcp_compat_check.py`.

## Verdict format
Per track: PASS / PASS WITH RESERVATIONS / FAIL, the evidence, and any finding with a minimal reproduction. A finding you can
reproduce moves its register entry to FAILED; do not edit the register yourself.
