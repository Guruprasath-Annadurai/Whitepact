# Phase 2 — Antigravity independent audit handoff

**This document is a handoff. It is not an Antigravity PASS.**

## Candidate under review

Review the successor branch `cursor/whitepact-global-launch-execution-d20d`, whose parent is:

- SHA `0cdef3947503adf7c3f08a5116a4808deda1d3f7`
- Tree `b20ea9d9ab849f3d49ae51fa47ecfabc64b8f865`

Also re-check that green SHA itself. The memory-scope defect is present there and absent only after the successor fix in `src/responsibleai/governance/models.py`.

Qualified ancestors already recorded by prior milestones, and not re-qualified here:

- M4 `52d9b3c5497af24bb7d4a7147e33deaadc64296e`
- M5 `46685fad1ad49cfde36341ea1fad146ce1d2e714`
- M6 `ee6e4a26becf7e89a933202651fba3b4e7a8176d`
- Integrated lanes tip inside this history: `35488a68e587df2adfdb1ceaad44001faca524a4`

PR #168 HEAD `ae9e59057bdc69bd7681275db0daef7b815241e2` is **not** an ancestor of `0cdef394`. Do not treat the RC as containing that ecosystem tip.

## Environment

- Python 3.11 and 3.12.
- Repository checkout with full PR history for the DCO test (`git fetch --unshallow` or `fetch-depth: 0`).
- PostgreSQL only for suites that declare a database fixture. The commands below do not need it.
- No cloud credentials. Do not apply Terraform.

## Commands Cursor executed

From the successor worktree, with `PYTHONPATH` set to that tree's `src`:

```bash
python -m pytest \
  tests/test_authority_attenuation.py \
  tests/test_governance_core.py::TestGatewayAttenuation \
  tests/test_property_based.py::TestAttenuationProperties \
  tests/test_release_evidence_check.py \
  tests/test_dco_historical_exception.py \
  tests/test_pinned_actions.py \
  -q --tb=line --override-ini='addopts='
```

Observed on the successor before the documentation commit: the governance, DCO, and evidence slice reported `61 passed`. The pin-checker file was then added and `tests/test_pinned_actions.py` plus `TestMemoryScopeEscalation` plus the evidence checker reported `20 passed`. Re-run the union on the exact successor HEAD. Do not copy these counts forward if the tree changes.

```bash
python scripts/check_pinned_actions.py
python scripts/release_evidence_check.py docs/launch/evidence/rc-0cdef394.json
```

Expected pin result: `All GitHub Actions dependencies are pinned to immutable commit SHAs.`

Expected evidence result: exit code 1, decision `NO-GO`, `accepted` empty, `declared` only `ci.canonical`, artifact verification `UNVERIFIED`.

Terraform, local, no credentials:

```bash
terraform version   # this session: Terraform v1.9.8
for env in development staging production; do
  terraform -chdir="infra/terraform/environments/$env" init -backend=false -input=false
  terraform -chdir="infra/terraform/environments/$env" validate
done
terraform fmt -check -recursive infra/terraform
```

Observed: all three roots `Success! The configuration is valid.` Format check exited 0.

## Matrix Antigravity should execute

Each row needs a positive case, a negative case, and, where the row says so, an adversarial or concurrency case. Existing suites are anchors, not a substitute for independent execution.

| Control | Anchor | Expected |
|---------|--------|----------|
| Constitution / policy | `tests/test_governance_core.py` | Explicit deny stays deny |
| Identity | `tests/test_web_platform.py` | Unknown password reset is indistinguishable |
| Authority ceiling | `tests/test_org_authority_ceiling.py` | Child cannot exceed org ceiling |
| Delegation attenuation | `tests/test_authority_attenuation.py` | Wider `memory_scope`, value, targets, hours, or actions deny |
| Transitive delegation | `tests/test_property_based.py` | Subset passes; extra action type escalates |
| Intent / risk | gateway evaluate path | Intent violation denies before execution |
| Human approval | `tests/test_v1_customer_journey.py` | Approval required does not execute early |
| Grants | governance execution tests | Grant required for consequential execution |
| Nonce / replay | grant and TOTP replay suites | Second use fails closed |
| Revocation | revocation kernel tests | Revoked authority does not execute |
| Tenant isolation | `tests/test_pg_cross_tenant_authority.py` | Cross-tenant read and write fail |
| MCP transport | `tests/test_mcp_ws2_authority_matrix.py` | Stdio does not bypass governance |
| SDK / CLI | SDK contract tests | Same deny as the API |
| API / UI | `tests/test_v1_web_contract_closure.py` | UI cannot call a path the API would deny |
| Egress | WAR-8 egress harness | Private and unapproved destinations fail |
| Evidence integrity | evidence bundle tamper tests | Modified evidence fails verification |
| Audit | tenant-scoped audit tests | Caller sees only its tenant |
| Database failure | migration preflight tests | Corrupt history fails closed |
| Sessions / RBAC | web platform and invitation adversarial tests | Role change is enforced on the next call |

## Memory-scope case that must fail closed

Parent `memory_scope` `org:acme`. Child `memory_scope` `org` or unset. `validate_attenuation` and `WhitePactRuntimeGateway.evaluate` must deny with `DELEGATION_AUTHORITY_ESCALATION` and field `memory_scope`.

Sibling `org:acme2` must also deny. Descendant `org:acme:agent:bot1` must not be treated as escalation.

On SHA `0cdef394`, the wider child currently passes `validate_attenuation`. That is the defect. The successor must fail it.

## Do not

- Describe Cursor's pytest output as an Antigravity result.
- Merge this branch while retesting.
- Weaken coverage thresholds to make a run green.
