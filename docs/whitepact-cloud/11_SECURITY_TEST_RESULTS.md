# Security Test Results

Environment: **authorized simulation and unit tests only** unless noted.

| # | Scenario | Expected | Status | Evidence |
|---|----------|----------|--------|----------|
| 1 | Unauthorized employee login | Deny | TESTED_IN_SIMULATION | Access JWT tests |
| 2 | Access outside role | Deny | VERIFIED | `test_developer_cannot_receive_iam_write` |
| 3 | Stolen session replay | Deny | TESTED_IN_SIMULATION | grant `consumed` |
| 4 | Terminated employee | Deny | VERIFIED | `offboarding.py` tests |
| 5 | Privilege escalation | Deny | VERIFIED | role_allows |
| 6 | Unauthorized device | Deny | NOT_TESTED | needs Access device posture |
| 7 | Forged identity header | Deny | VERIFIED | `test_rejects_forwarded_identity_header` |
| 8 | Direct origin access | Block/deny | NOT_TESTED | needs live CF+LB |
| 9–25 | Lateral movement, egress, DR, etc. | Per threat model | NOT_TESTED or BLOCKED | no live staging |

Retest after owner-approved staging provisioning.
