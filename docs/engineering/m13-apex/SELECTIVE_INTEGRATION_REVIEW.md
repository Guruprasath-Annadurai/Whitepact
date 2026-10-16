# Selective TITAN integration review

Source candidate40e43440489eebde6886af014943ea18ed228b68,
tree c6b106db0974838f084e391ca8f8b2f084c45882.
Merge base with APEX:8cb692b99fb4b1fa894e07d432105209f430b0f7.
No whole-branch import or protected-test/manifest replacement.

## Qualified product selection: APEX-ORG-01

`src/responsibleai/db/org_repository.py` now matches the reviewed TITAN blob
`4e104e107b84ff0b245b39065b51d978c841d85a` exactly. It adds an optional
expected-name predicate to the existing organization-specific UPDATE, allowing
one atomic compare-and-set winner and preserving the previous call signature.
No overlap with Forge/APEX changes existed in this file.

`src/responsibleai/dashboard/app.py` overlaps Forge product work. Only the
organization request model and existing rename route were selectively adapted;
Forge summary/record serialization and all unrelated routes remain in place.
TITAN's specific path alias and name precondition are included. Its first-nonempty
workspace-precondition selection was **not** accepted unchanged: independently
reproduced200 when path matched but body required another organization. APEX
requires every supplied path/body/header context to agree with the existing
authenticated organization. Conflicts return409 without rename. Existing session,
CSRF and OWNER/ADMIN checks remain; no privileged authority feature enabled.

Evidence:
- Owner rename test on original APEX:1FAIL (stale context accepted200).
- Independent conflicting-context test on TITAN:1FAIL (200 vs409).
- Unchanged owner rename test against selected APEX source:1PASS,4.15seconds.
- New authenticated tests:2PASS,7.62seconds. An initial viewer fixture incorrectly
  attempted to demote an owner, which correctly did nothing; corrected to an
  explicit viewer fixture before acceptance. No role-enforcement defect claimed.
- Expanded organization/directory/receipt run19PASS, zero skips,82.71seconds,
  including SQLite and real PostgreSQL concurrent compare-and-set, exactly one
  winner. Cross-worktree pytest files were run separately after a conftest import
  collision; that collision was a harness issue, not a product failure.

## Deferred security selection

TITAN modifies14 source/migration files including root/consent/delegation,
revocation epochs, first-passkey bootstrap, WebAuthn origins and runtime admission.
Root identity qualification remains blocked. Forward migration preservation has
independent evidence, but nonempty rollback loses security state. Full independent
security-sensitive acceptance and source review remain required before selecting
those hunks. Original immutable tests/manifests remain APEX versions. This product
selection does not qualify the unintegrated TITAN kernel or complete checkpointA.
