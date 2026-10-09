# WhitePact issue register

Authoritative register for the integration candidate that continues PR #175. It is not a production authorization and not an Antigravity verdict. Counts below are only the issues inspected and recorded in this file. They are not a repository-wide completion percentage.

Integration base before these fixes: `8aea364ac586e6498fefc4fa37de55a7e25c1bf7`, tree `10b814e2800685446d0deb88afe972cf64eccee6` (`cursor/whitepact-unified-security-9d8c`, PR #175). `origin/main` at inspection was `38f927229b4ea53d19a9107c78653307f5263629`.

| ID | Subsystem | Severity | Reproduction | Root cause | Fix | Commit | Test evidence | CI | Antigravity | Disposition |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TB-01 | Identity | P1 | Hosted MCP accepted a trusted VC whose `orgId` was missing or not in `organizations`. Dashboard OIDC and SAML did the same and stored `Plan.FREE`. | Verified token claims were treated as tenant membership. Hosted OIDC already returned no context. VC, dashboard OIDC, and dashboard SAML did not. | Refuse the session unless `get_org` returns the claimed organization. | `1e75790f68902f01f9a16bf04d904f2ac732045d` | `tests/test_mcp_verified_principal.py`, `tests/test_saml_app_routes.py`, `tests/test_final_coverage_batch13.py` | This candidate's GitHub Actions run, not yet a pass | Required | ENGINEERING_FIXED — INDEPENDENT RETEST REQUIRED |
| TR-01 | Trust gates | P2 | A2A and LangChain text said network errors fail open. `TrustCheckResult.passes` already returned false. Outages were described as "require_known=True". | Stale security claims after the fail-closed change in `passes()`. | Docstrings and block reasons name lookup failure, staleness, low score, or unknown record. Behavior of `passes()` is unchanged. | `1b974d5f83c875891322884530baef6e5fe0cbc7` | `tests/test_a2a_adapter.py` | This candidate's GitHub Actions run, not yet a pass | Required | ENGINEERING_FIXED — INDEPENDENT RETEST REQUIRED |
| FH-01 | Egress | P1 | Ancestor reproduction: unrestricted `tcp dport 443 accept` after the authority allowlist. | First-match nftables. | Already on the integration base. Not reopened. | `db667d8b8e561ecf77b1e1c90231800b9fb38332` | `tests/test_foundation_hardening.py` on the base | PR #175 checks were still running for Python 3.11 and 3.12 at inspection | Required on this tree | Inherited fix. Not independently verified on this tip. |
| FH-02 | Trust admission | P1 | Gateway ALLOW on `trust_state.error`. | Outage and unknown model shared one branch. | Already on the integration base. | `1b6a6abe2cec6a368ff1c53d6bd790582246b58e` | `tests/test_governance_trust_state.py` | Same as FH-01 | Required on this tree | Inherited fix. |
| FH-03 | Rate limit | P2 | Rotated dashboard tokens multiplied the ceiling. | Key was the bearer hash. | Organization key after `audit_org_id` is set. | `ebd2e102ee364b6006db4f3fa73a6d0846dd6c53` | Foundation hardening tests | Same as FH-01 | Required on this tree | Inherited fix. |
| FH-04 | MCP auth | P2 | Rotated bearer tokens reset the source failure budget. | Peer ceiling defaulted above the credential ceiling. | Peer ceiling equals the credential ceiling. | `ebd2e102ee364b6006db4f3fa73a6d0846dd6c53` | MCP transport tests | Same as FH-01 | Required on this tree | Inherited fix. |
| FH-05 | Policy | P2 | A later DENY could sit behind a covering ALLOW. | First-match evaluation. | Persistence rejects the shadow. | `eb46b23b4942c05c2c827d59a35889d86c247cc8` | Foundation hardening tests | Same as FH-01 | Required on this tree | Inherited fix. |
| FH-06 | Evidence | P2 | Hash-chain recomputation was described as tamper evidence against a database administrator. | `verify_chain` trusts stored rows. | Wording and offline witness. Live publication is not deployed. | `7981756e54f74713cc72fcf07c6efd2201c60af2` | Attestation tests | Same as FH-01 | Required on this tree | EXTERNAL_BLOCKER for live anchoring |
| FH-07 | Runtime | P2 | Production multi-replica with sqlite or memory limits only warned. | Startup did not enforce shared backends. | Production startup raises. | Inherited with the foundation commits | Foundation hardening tests | Same as FH-01 | Required on this tree | Inherited fix. |

## Local test evidence for TB-01 and TR-01

Command:

`pytest tests/test_mcp_verified_principal.py tests/test_saml_app_routes.py tests/test_final_coverage_batch13.py::TestIdentityResolutionBatch13 tests/test_a2a_adapter.py tests/test_langchain_middleware.py`

Result: 59 passed on Python 3.12.3. This is not the full matrix and not a CI pass.

## Still open, not counted as fixed

| ID | Severity | Disposition |
| --- | --- | --- |
| LIVE-ANCHOR | P1 for enterprise evidence claims | EXTERNAL_BLOCKER. Database hash chains are not proof against a privileged database operator. |
| STAGING-PROVISION | Release blocker | Owner string `APPROVE STAGING CLOUD PROVISIONING` is absent. No Terraform apply, DNS change, or paid provisioning was performed. |
| ORIGIN-AOP | Release blocker | Cloudflare client CA, origin certificate, and hostname are absent. `origin_client_certificate_enforced` stays false. |
| PYPI-RENAME | P0 historical, distribution | Published name remains `rai-governance-platform`. No publish in this change. |
| LOAD | Unverified | No new p50, p95, or p99 measurement was taken on this tip. |
| PROD-GATES | Release blocker | Backup restore, live isolation, production secrets, and rollback were not executed. |

## Release gates

| Gate | State |
| --- | --- |
| Public open-source release | Not approved. Independent qualification of this tip is absent. |
| Directory submission | Not submitted. Claims must stay inside the Codex contract. |
| Enterprise hosted production | NO-GO. |
| Merge to `main` | Not performed. |
