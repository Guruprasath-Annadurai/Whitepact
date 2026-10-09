# Antigravity review handoff

**From:** Cursor, zero-budget preparation
**Date:** 2026-10-09
**Verdict requested:** pass, fail, or conditional on *this package only*
**Not requested:** staging GO, production readiness, or closure of CLOUD-AG-01–07

## What you are reviewing

A plan-only development candidate:

- `docs/zero-budget/` — eligibility, architecture, exact allocation, boundaries, rollback, cost register
- `infra/zero-budget/oci/` — Terraform for one Always Free Ampere VM, validated with `terraform validate` against `oracle/oci` 7.32.0
- `infra/zero-budget/oci/apply.sh` — always exits 2
- `infra/zero-budget/oci/preflight.py` — offline allocation and forbidden-resource checks
- `.github/workflows/zero-budget-iac.yml` — validate and preflight only

No cloud API create or destroy was called. `terraform plan` with
`authorization_gate=HOLD` failed the precondition in `checks.tf` (local
run, dummy credentials, 2026-10-09). That failure is the intended gate.

## Out of scope, still open

| Item | Where it continues |
|---|---|
| PR #173 Phase 3/4 staging preflight, NO-GO | `cursor/whitepact-phase34-staging-preflight-00f5` |
| PR #174 authority egress, trust admission, evidence claims | `cursor/whitepact-foundation-hardening-934e` |
| Enterprise cloud staging | `docs/phase0/ANTIGRAVITY_CLOUD_PRESTAGING_AUDIT_REGISTER.md`, verdict **BLOCKED — UNSAFE TO PROVISION** |
| Live reference deployment (Render, Supabase, Upstash) | Not modified |

Please do not treat a pass on this handoff as permission to provision, and
do not treat it as remediation of the seven CLOUD-AG findings. Those
findings remain open. In particular:

- CLOUD-AG-02: the security list, metadata drop, and Bastion path are still design-only. There is no live apply proof, by restriction.
- CLOUD-AG-03 and CLOUD-AG-07: Cloudflare Access and origin protection are not in this design.
- CLOUD-AG-01 and CLOUD-AG-04: this VM does not enable the privileged executor or a public admin control plane. Absence is not a fix.

## Claims to challenge

1. Always Free Ampere is now 2 OCPU and 12 GB (1,500 OCPU-hours and 9,000 GB-hours), not 4 OCPU and 24 GB. Source: Oracle Always Free Resources, retrieved 2026-10-09.
2. `VM.Standard.E2.1.Micro`, GCP `e2-micro`, and AWS micro shapes are below the repository's 4 GB dev floor (`DEPLOY_RUNBOOK.md`).
3. A private OCI subnet was rejected because egress would require a paid NAT gateway. The substitute is an ephemeral public IP plus a security list with no internet ingress. That substitute is weaker. The handoff says so.
4. Pinned `python:3.12-slim`, `node:22-alpine`, `postgres:16-alpine`, and `redis:7-alpine` indexes include `linux/arm64/v8`. The WhitePact image was **not** built on ARM here.
5. Neon Free and Cloudflare Free are test-only and do not satisfy enterprise tenant or authority requirements. No RLS exists in this repository.
6. Budget alerts do not guarantee a $0 bill. The documented budget is still $0, enforced by not creating resources.
7. Existing AWS credit balance is **unknown**. The new-account "up to $200" offer is not a measurement of this account.
8. GCP billing state is **unknown**. A Gemini billing link is recorded historically and must be treated as Paid until the console says otherwise.

## Checks already run

| Check | Result |
|---|---|
| `python3 infra/zero-budget/oci/preflight.py --self-test` | Passed. Drift of memory 12 → 24 is detected. A NAT gateway resource is detected |
| `infra/zero-budget/oci/apply.sh` | Exit 2 |
| `terraform init -backend=false` and `terraform validate` | Success, provider `oracle/oci` 7.32.0 |
| `terraform plan` with `authorization_gate=HOLD` | Failed precondition. No apply |
| Image index platforms | `linux/arm64/v8` present on the four pinned indexes |
| Repository visibility | Public |

## Questions for the review

1. Is the public-subnet tradeoff acceptable for a synthetic dev VM, or must persistent compute wait until a $0 egress path without a public IPv4 exists?
2. Is consuming the entire 2 OCPU / 12 GB quota on one instance the right cost control, given idle reclamation can then remove the only host?
3. Does any statement in `docs/zero-budget/` over-claim readiness? The intended status line is: gate closed, not staging GO, not production ready.
4. Is the quota statement pair (`standard-a1-core-count`, `standard-a1-memory-count`) sufficient, or do you want a block-storage quota added before any future authorization? Block storage is currently limited only by this module's 50 + 50 GB values, not by an OCI quota.
5. Should GitHub Actions remain the only authorized test plane until OCI capacity and the card-on-file risk are accepted in writing?

## Reply format

| Question | pass / fail / conditional | Note |
|---|---|---|
| 1 Public IPv4 versus paid NAT | | |
| 2 Full-quota single VM | | |
| 3 No readiness over-claim | | |
| 4 Block-storage quota gap | | |
| 5 Actions-only until OCI sign-off | | |

Overall: **pass / fail / conditional**. A conditional pass still does not open the authorization gate. Opening the gate is a separate owner action plus a reviewed change to `apply.sh`.
