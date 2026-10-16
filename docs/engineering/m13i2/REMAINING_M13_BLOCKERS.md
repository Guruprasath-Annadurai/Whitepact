# Remaining mandatory M13 blockers

| Gate | Status and owner disposition |
| --- | --- |
| Real passkey browser ceremony | BLOCKED by backend expected origin versus actual application origin; security owner |
| Complete customer authority journey | BLOCKED after the first passkey challenge; no consent/root/delegation/execution fixture substitute |
| Application ownership inventory | BLOCKED pending verified tenant-scoped backend contract |
| Effective executable capabilities | BLOCKED; registration and backend record presence must not imply permission |
| ATLAS PR #212 qualification | NOT integrated: local origin mismatch fixed in observed run, but defensive production-origin invariants fail; capability consent/policy/expiry and atomic cascade guarantees remain unqualified |
| Organization rename across concurrent workspace changes | BLOCKED UI mutation: existing pathless PATCH binds current cookie organization and lacks expected-organization/version precondition; ordinary fresh-session HTTP success does not qualify this race |
| Inherited full lint | OPEN: I1 measured 101 errors in security-owned source/tests; retained gate, no blanket exclusions |
| Inherited DCO | OPEN: security checkpoint `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc` lacks signoff; authors/maintainers must disposition |
| Historical aggregate CodeQL and SDK timeout | Not cleared merely by unrelated fresh passes; exact failing-run owner disposition still required |
| Full dependency vulnerability / supply-chain acceptance | Pinned-action, license and trust controls pass; these do not substitute for a new complete dependency/CodeQL acceptance receipt. GitHub push reported four default-branch advisories; candidate applicability is unqualified |
| Production acceptance | GLOBAL PRODUCTION NO-GO; no milestone-complete or M14 authorization |
| Founder / inherited security decisions | Path B 300-second lifetime decision remains pending; original security registers remain authoritative and unchanged. Linear SHA-256 evidence chains are not claimed as Merkle proofs |
| Incident / recovery / full browser authority acceptance | No fresh incident/recovery authority contract or real authenticator journey was independently qualified. Preparation remains gated; native CI passes do not prove physical multi-host crash recovery |

Fresh I2 results and limitations are recorded in the individual reports and PR. I1 results remain historical evidence and are not relabeled as I2 execution.
