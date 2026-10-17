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

## Qualified transport selection: APEX-MCP-02

Source TITAN-2 commit6b604bf12ac07508c5b584b85ed48df8a983e5af; detached review.
Owner-authored new SSE/PostgreSQL/runtime suites14PASS/0SKIP,97.41seconds;
preserved transport/authentication/revocation subset76PASS/0SKIP,136.29seconds.
These are scoped assertions, not complete external runtime qualification.

Independent real-TCP SSE test opens an actual session with actual fixture keys,
initializes through the emitted endpoint, and posts harmless pings. No manual
transport-owner dictionaries are seeded. Original APEX accepts an unauthenticated
ping202 instead of401 (reproduced FAIL). Candidate rejects absent/invalid401,
cross-tenant403, sibling-credential403 and revoked401; owner credential remains
functional202 with real SSE reply. Same test PASSes on candidate,4.28seconds.
Fixture protocol authorization does not qualify customer root authority.

Select only `src/responsibleai/mcp/server.py`; it exactly matches owner blob
5c712437505e9711854bf08e03c89a69e43a5f2b. Prior APEX server blob exactly matched
owner parent, so no conflict or obsolete source restoration. APEX `tools.py`
advisory/external-boundary metadata is preserved. Integrated source subset
85PASS/0SKIP,143.91seconds. Full MCP scope is added to both independent Python CI
jobs with explicit zero-skip enforcement; final results recorded in PR receipt.

SDK support floor tightened consistently to mcp>=1.29.1,<2 in core/optional/dev
requirements, matching independently exercised session-owner APIs. Older SDKs
are not advertised as qualified. The upper major-version boundary is preserved.
No nonce, in-flight or container-backend changes from TITAN-2 are selected here;
they remain separately reviewed owner work. Root FK and rollback blockers remain.
