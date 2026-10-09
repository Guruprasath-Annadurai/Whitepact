# Phase 5 — Customer journey gap matrix

**Gate: CONDITIONAL.** Code for these journeys exists on the release candidate. This session did not re-run the full customer suite or a browser pass. One governance defect on the delegation path was reproduced by reading `validate_attenuation` and closed with tests.

| ID | Journey | On `0cdef394` | This session | Launch note |
|----|---------|---------------|--------------|-------------|
| A | Registration | `tests/test_v1_customer_journey.py`, web identity repository | Not re-run | Needs staging email delivery proof |
| B | Login, logout, reset, session | `tests/test_web_platform.py` | Not re-run | Reset must stay single-use |
| C | Organization create | Enterprise router / service | Not re-run | |
| D | Invitation accept and revoke | `tests/test_web_invitations_adversarial.py` | Not re-run | |
| E | RBAC | Enterprise roles and web contract tests | Not re-run | |
| F | Agent registration and authority | Delegation repository calls `validate_attenuation` | **Defect fixed** | Wider `memory_scope` must deny |
| G | Policy versioning | `governance/policy_lifecycle.py` | Not re-run | |
| H | Tool registration | MCP tool surface | Not re-run | |
| I | Human approval | Customer journey and approval module | Not re-run | |
| J | Short-lived grant | Governance execution | Not re-run | |
| K | Authorized execution | Gateway allow path | Descendant memory scope allowed in unit test | |
| L | Denied execution | Gateway deny path | Widened memory scope denied in unit test | |
| M | Expired grant | Authority lifetime tests | Not re-run | |
| N | Replay | Grant / TOTP replay suites | Not re-run | |
| O | Tenant isolation | `tests/test_pg_cross_tenant_authority.py` | Not re-run | Live two-tenant proof still required |
| P | MCP | `tests/test_mcp_ws2_authority_matrix.py` | Not re-run | |
| Q | SDK / API | SDK contract tests | Not re-run | |
| R | Evidence and audit export | Evidence and SIEM suites | Not re-run | |
| S | Revocation and key rotation | Revocation kernel; `scripts/rotate_field_encryption_key.py` | Not re-run | Live rotation not performed |
| T | Cancellation and deletion | Data lifecycle tests | Not re-run | Retention period is an owner decision |
| U | Dependency failure | Migration preflight and health paths | Not re-run | Needs a real database stop test in staging |
| V | Accessibility and keyboard | CI Accessibility (WCAG2AA) passed on `0cdef394` | Not re-run in a browser here | Do not claim a new audit |

No journey was replaced with a frontend mock. Unfinished commercial behavior is listed in Phase 7 as an owner decision rather than hidden.

## Gap that was real

`validate_attenuation` enforced action types, value caps, targets, delegation depth, approval flags, and hours. It did not enforce `memory_scope`. A child authority could be granted `org` while its parent held `org:acme`. Later checks used only the child scope, so the widening survived grant time.

## Gate

CONDITIONAL until Antigravity retests the memory-scope case and a staging run repeats journeys A–V on the successor SHA.
