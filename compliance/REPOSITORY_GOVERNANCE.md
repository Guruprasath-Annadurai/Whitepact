# Repository Governance Evidence

Verified through authenticated GitHub API reads on 2026-08-30. This is a point-in-time
configuration record, not continuous proof.

## Current `main` protection

| Control | Evidence | Status |
|---|---|---|
| Pull request required | Classic branch protection exposes PR-review configuration | VERIFIED |
| Required status checks | Strict/up-to-date; CI 3.11/3.12, build, Helm, DCO, Gitleaks, accessibility, i18n | VERIFIED |
| Force pushes | disabled | VERIFIED |
| Branch deletion | disabled | VERIFIED |
| Conversation resolution | required | VERIFIED |
| Admin enforcement | enabled | VERIFIED |
| Stale review dismissal | enabled | VERIFIED |
| Human approval | required count is 0 | HUMAN MATURITY BLOCKER |
| Code-owner review | not required | HUMAN MATURITY BLOCKER |
| Signed commits | not required | NOT APPLICABLE to release identity; signed tags are the release-intent control |
| Rulesets | none; classic protection is authoritative | VERIFIED |

The repository has one genuine maintainer. Requiring one non-author approval today would
make all legitimate changes impossible; setting approval count to zero is therefore
honest but does not satisfy independent review. `.github/CODEOWNERS` assigns only the
actual owner.

## Release governance

`RELEASING.md`, `security/release-signers.allowed`, and
`compliance/SIGNED_VERSION_TAGS.md` define signed annotated tags and the approved signer
boundary. Release publication uses GitHub OIDC/PyPI Trusted Publishing rather than a
long-lived PyPI token. The reusable trusted-builder architecture is on `main`; `v1.2.6`
successfully exercised signed release intent, hosted reproducible builds, provenance and
SBOM attestations, independent verification, exact-byte PyPI publication, PyPI hash
confirmation, and GitHub Release creation. `compliance/SLSA_BUILD_PROVENANCE.md` records
the release-specific evidence and claim boundary.

## Owner actions after this branch merges

1. In **Settings → Branches → main**, add `Dependency Review`, `OpenSSF policy checks`,
   `Reproducible build verification`, and the security scan if its runtime is acceptable
   on every PR to the required checks list; retain strict/up-to-date mode.
2. Confirm bypass is limited to the repository administrator and emergency use is logged.
3. When a genuine second reviewer is authorized, set required approvals to at least one,
   require code-owner review for security/release paths, and require approval of the most
   recent push. Do not do this with a synthetic account.
4. Review branch settings quarterly and after ownership or GitHub-plan changes.

Steps 1–2 are **OWNER ACTION REQUIRED** because repository configuration is outside the
reviewable branch and must follow workflow merge/name stabilization. Step 3 is a
**HUMAN MATURITY BLOCKER**.
