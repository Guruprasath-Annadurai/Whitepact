# Remaining mandatory M13 blockers

| Gate | Status and owner disposition |
| --- | --- |
| Real passkey browser ceremony | BLOCKED by backend expected origin versus actual application origin; security owner |
| Complete customer authority journey | BLOCKED after the first passkey challenge; no consent/root/delegation/execution fixture substitute |
| Application ownership inventory | BLOCKED pending verified tenant-scoped backend contract |
| Effective executable capabilities | BLOCKED; registration and backend record presence must not imply permission |
| Inherited full lint | OPEN: I1 measured 101 errors in security-owned source/tests; retained gate, no blanket exclusions |
| Inherited DCO | OPEN: security checkpoint `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc` lacks signoff; authors/maintainers must disposition |
| Historical aggregate CodeQL and SDK timeout | Not cleared merely by unrelated fresh passes; exact failing-run owner disposition still required |
| Production acceptance | GLOBAL PRODUCTION NO-GO; no milestone-complete or M14 authorization |

Fresh I2 results and limitations are recorded in the individual reports and PR. I1 results remain historical evidence and are not relabeled as I2 execution.
