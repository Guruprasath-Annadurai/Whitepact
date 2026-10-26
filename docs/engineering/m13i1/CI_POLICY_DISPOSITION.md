# M13-I1 inherited policy and CI disposition

**Policies remain enforced. No protected history rewritten. Overall integration remains BLOCKED.**

PR #208's failed runs were read directly: CI `38740660335`, DCO `38740660389`, OpenSSF `38740660479`. PR #209's eighteen product checks were independently verified successful at its exact issued HEAD; that narrower product matrix did not discharge inherited policy failures.

| Gate | Exact cause / evidence | Disposition |
| --- | --- | --- |
| OpenSSF | Missing copyright/SPDX headers in `test_crewai_llamaindex_governance_consumers.py` and `test_wave1_framework_compatibility.py` | **FIXED** by header-only additions to those product-owned tests. Source-header, action-pin and trust scripts pass. No exclusions changed. |
| DCO on historical security range | Failed log identifies unsigned commits `39619c4b…`, `57c69344…`, `f7bf1729…`, `a0d941c3…`, `4f383ffe…`, `97657ece…`, `128f988a…`, `0daa57aa…`, `6062290c…`, `15e0c624…` | **BLOCKED / OWNER DISPOSITION REQUIRED**. Reviewer cannot sign for original authors, add exceptions or rewrite protected ancestry. New integration commits use genuine configured-committer signoffs. Existing exceptions remain unchanged. |
| Introduced DCO in new stacked PR | The introduced security documentation commit `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc` has no trailer | Dedicated exact-range DCO job intentionally retains this failed gate; merge signoff is not a substitute. |
| Ruff in full CI | 101 current diagnostics across security source and tests, including original reproducers | **BLOCKED**, formal security-owner handoff. No scanner suppression or broad autoformat changes to preserve originals. |
| Full Ruff breakdown | authority service 10; original reproducer files 4; customer-root tests 11; delegation-revocation 5; root-hardening 24; R3 9; M13-S 1; approval-resume 16; Linux-containment 9; revocation-outage 12 | Dedicated CI keeps the full `ruff check src/ tests/ sdk/python/` gate. The two F821 diagnostics are postponed `Any` annotations in root-hardening tests, not a demonstrated runtime bypass. |
| TS SDK hanging body | Historical CI's `getAttestation` test observed `unbounded` after 3 seconds instead of `AbortError` | **NOT REPRODUCED in fresh 53-test run**, not declared fixed or flaky-safe. No timeout/assertion changed; repeat exact-head CI remains required. |
| Candidate tree guard | Historical synthetic merge `9d16ab52…` tree `45b2db38…` differed from security candidate tree `06f9add5…` | Failed guard was truthful; do not waive it. Dedicated integration jobs explicitly checkout event HEAD and record tree/parents. No claim that old merge-tested CI was exact-head qualification. |
| Aggregate CodeQL | Individual language jobs passed but historical aggregate failed | Historical aggregate not cleared by product checks; no policy change. Owner rerun/analysis disposition required if required on final review target. |
| Golden journey | Actual run returns BLOCKED at passkey origin and lacks downstream authority/action proof | Dedicated customer job preserves nonzero exit; no continue-on-error or expected-pass wrapper. |

The new integration workflow reports security assertions, native-container scope, inherited policy gates and customer journey separately. Green subsets never override failed mandatory gates. Existing main-targeted workflows and their coverage/security policies are not weakened. Final exact-head job results and links are recorded in the draft PR after execution; pending/failed/skipped jobs are not passes.
