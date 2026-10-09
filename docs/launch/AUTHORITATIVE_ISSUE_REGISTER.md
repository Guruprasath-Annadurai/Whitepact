# Authoritative issue register

This file is the current register for the launch-gate candidate branched from `8aea364ac586e6498fefc4fa37de55a7e25c1bf7` (PR #175). It does not replace historical registers. Those files stay as records of earlier reviews. They are not deleted.

Superseded for current status, kept on disk:

- `docs/phase0/PHASE0_OFFICIAL_DEFECT_REGISTER.md` records the pre-remediation baseline. Later milestones closed several of those rows. This register does not reopen a row that a later qualified ancestor closed, and it does not treat that ancestor's pass as a pass of this candidate.
- `docs/enterprise/M6_DEFECT_REGISTER.md` remains the M6 engineering ledger. M6's independent pass is `ee6e4a26becf7e89a933202651fba3b4e7a8176d`, an ancestor of this branch. It does not qualify commits after that SHA.

No GitHub issue was closed by this register.

## Inherited foundation controls

FH-01 through FH-07 are present via the PR #175 cherry-picks. Local regression coverage is `tests/test_foundation_hardening.py`. Antigravity has not signed this candidate. Live evidence publication remains `EXTERNAL_BLOCKER`.

## Findings on this candidate

| ID | Severity | Status | Evidence |
| --- | --- | --- | --- |
| LG-01 | P1 | Engineering fixed. Independent retest required. | Container runner treated a missing `responsibleai` import as a successful echo. `6b9115f`. `tests/test_launch_gate_isolation_runner.py`. |
| LG-02 | P1 | Engineering fixed. Independent retest required. | Hosted metering recorded `allowed=True` before governance, so a denial consumed quota. Hosted execution with no usage repository now returns `quota_enforcement_unavailable` and does not call governance. `87e762c`. `tests/test_launch_gate_hosted_metering.py`. |
| LG-03 | P1 | Engineering fixed. Independent retest required. | Resume substituted `unknown` when `requested_by` was blank. `c535770`. `tests/test_launch_gate_resume_identity.py`. |
| LG-04 | P2 | Open. | `DockerContainerBackend` still runs a caller-supplied `runner.py` from `workspace_files`. `IsolationBroker` does not pass workspace files. Direct backend callers can still replace the entrypoint. |
| FH-06-LIVE | P2 | Blocked. | Offline Ed25519 head witness is local. Live anchoring is not deployed. |
| CLOUD-STAGING | Blocker | Blocked. | Owner approval `APPROVE STAGING CLOUD PROVISIONING` is not granted. No Terraform apply, DNS change, or billing activation was performed. |

## Open counts on this candidate

Confirmed open P0 in the paths changed here: 0. That is not a whole-product absence claim.

Open P1 in the paths changed here: 0, pending independent retest of LG-01, LG-02, and LG-03.

Open P2: LG-04, FH-06-LIVE.

Open external blocker: CLOUD-STAGING, plus Cloudflare origin material, a real hostname, and a Hetzner billing alert. Those remain outside this tree.
