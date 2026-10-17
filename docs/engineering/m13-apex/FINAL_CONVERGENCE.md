# Final convergence — active qualification ledger

M13 OPEN. GLOBAL PRODUCTION NO-GO.

Base APEX af809ac720384e97d3cf4056b32d8fd623014874, tree
22eae2f0c8a6065cfd73e4f424edeab25aba90af. Separate convergence worktree;
original APEX checkout, owner branches and original reproducer files preserved.
Verified owner TITAN-1 e5c29966d49cb910989e1379b60a0c4d6c364df0,
tree1f816bc6cc93a6d6b25b0167685757f2f40f3415, parent2819be09.
Verified TITAN-2 ae680621ed85b976b8496dcfdab093f5f4e5829f,
tree8955492c480102644ee95005eb67995bf09e886d, parent622b02d6.
PR218 merged only into owner development branch; PR217 remains open.

## Identity integration

Import reviewed initial-owner first-passkey qualification and final row-locked
revalidation. Preserve explicit grant/challenge session, organization, mailbox,
membership, expiration and freshness checks, WebAuthn RP/origin verification,
one-winner registration and no implicit root/session elevation from registration.
Owner security service matches PR217 behavior; differences are formatting.
Integrate passkey assertion cookie rotation and request-derived origin binding.
Reject owner router's extra traceback printing. Preserve normal error handling.

Integrate root actor lifecycle/tenant/recovery/identifier collision checks and
owner application/agent/delegation inventory APIs. Owner explicit persisted
membership, user and organization checks subsume the prior APEX helper at both
root boundaries. Do not treat mailbox BASIC assurance as external identity proof.
Retain stronger APEX directory validation (single email separator, nonempty
identifiers, E.164 phone syntax, metadata readback). Reject owner directory
regressions; do not import owner generated frontend, nonce/kernel or MCP changes.
Import APPLICATION enum and same-transaction delegation repository dependency.
Initial browser integration failures500 at application registration and delegation
were diagnosed as omitted dependencies and corrected, not relabeled BLOCKED.

## Additional runtime counterexamples

Accepted owner source reproduced three further failures: dead-worker tracking
deletion without container proof; persistence-write error leaving active tracking;
unresolved records ignored after same-process registry restart. New unchanged
counterexamples are in test_m13_convergence_tracking.py. Baseline3 FAIL.
Correction atomically persists tracking with file/directory fsync, propagates
write errors into admission denial/actual termination, preserves dead-worker
records, and persists unresolved status for registry restart. Unknown containment
continues to deny consequential admission. Native test additionally exercises an
actual exited child and independently inspected actual running Docker container.

Original test_kill_esrch_unlinks_dead_worker_tracking is retained verbatim and
FAILS because it mandates deleting the only evidence after worker death.
New counterexamples and neighboring runtime scope12 PASS/1 historical FAIL.
This historical contract requires explicit maintainer disposition; no skip,
assertion replacement or misleading GREEN claim. Whole-candidate gate stays RED.

## Version compatibility

Current application now checks the explicit supported PostgreSQL revision0065
before initializing/serving, even when auto_migrate=False. Missing/unreadable,
older/newer or multiple revision rows fail startup. A failed check disposes the
engine. Real PostgreSQL tests cover safe revision, rejected0064/0066, rollback,
restart and missing version table. Preserve existing0065 mandatory-passkey
downgrade refusal and original immutable migration reproducerf4d5731e9b2792b18a69e1fcfd475164ee4f0898.

This current-binary guard DOES NOT retroactively modify old0064 binaries.
Their historical startup/login counterexample remains unresolved. Database
credential retirement/version-specific roles or another independently qualified
database-side compatibility contract requires maintainer design/authorization.
No old binary is declared safe solely because the new binary rejects mismatches.

## Stage17 decision

Hosted reusable organization and service-account credentials require independently
qualified IDENTITY_VERIFIED. Canonical MCP OAuth complete_authorization also
starts from an existing API credential; it is not an agent signing-key bootstrap.
Delegation/inventory records and MCP review tokens are not execution grants.
No qualified existing agent-scoped authentication bridge has been established.
Creating a new credential class that bypasses the issuance policy would select a
new identity assurance policy, not merely wire existing product contracts.
Preserve the403 identity gate pending founder/identity-owner decision and legitimate
provider onboarding. No fabricated attestations or seeded approvals/grants.

## Evidence status

Local delegation/revocation neighbors19 PASS. Source Ruff PASS. Actual PostgreSQL
migration/startup matrix5 PASS. Additional real unresponsive CLI counterexample
demonstrated that per-command10s/5s limits exceeded the total cleanup budget;
each CLI timeout and retry sleep now respect the remaining total deadline.
New focused tracking/cancellation/cleanup scope17 PASS. Original historical
dead-worker-deletion assertion remains unchanged and RED.
Initial a887 runtime unit CI collection exposed an omitted owner test dependency;
the unchanged test_container_cleanup_race_adversarial.py is now included.
The new native matrix also challenges actual directory write denial and container
termination. Identity/root and genuine-browser qualification continue; only committed exact-head
receipts qualify final acceptance. Dedicated workflows retain original immutable
hash checks and run both supported Python versions and actual native Linux/Docker.
Historical Ruff/DCO/Gitleaks/migration assertion failures remain mandatory failures;
prior branch test success cannot substitute for integrated-head validation.

Dependency alerts independently inspected through the repository API: candidate
already pins source-map-js1.2.2, Mako1.4.3 and multidict6.9.1, meeting the first
patched versions reported by the three corresponding default-branch alerts.
Those default-branch alerts are not declared closed by a development branch.
Optional NLTK3.10.3 remains affected with no patched version reported; preserve
the existing opt-in/reachability disposition and require maintainer acceptance
or upstream fix. No alert is dismissed or scanner suppressed.
