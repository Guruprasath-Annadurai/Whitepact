# Maintainers

WhitePact currently has one authorized maintainer:

| Maintainer | GitHub | Responsibilities |
|---|---|---|
| Guruprasath Annadurai | [@Guruprasath-Annadurai](https://github.com/Guruprasath-Annadurai) | Repository administration, security triage, code review, releases, dependency updates, incident coordination, and policy maintenance |

No maintainer council or second authorized reviewer currently exists. This is a
human-maturity limitation, not an implied delegation to contributors.

## Decision and review responsibilities

- Changes enter through pull requests and must pass required checks.
- The maintainer validates scope, tests, security impact, documentation, and release notes.
- Release intent is expressed through the signed-tag and approved-signer process in
  [RELEASING.md](RELEASING.md).
- Security reports follow [SECURITY.md](SECURITY.md); operational escalation follows
  [the incident runbook](compliance/INCIDENT_RESPONSE_RUNBOOK.md).
- A change authored and approved by the same sole maintainer is not independent review.

## Adding or removing a maintainer

Maintainer access is granted only after sustained, attributable contributions and an
explicit written repository decision. The decision must update this file, CODEOWNERS,
repository access, release-signer evidence, and the continuity plan in one reviewed
change. Removal follows the same recorded process and includes credential revocation.

## Continuity

The current single-maintainer bus factor is one. The recovery and successor-access
work that can be prepared without inventing a successor is documented in
[compliance/PROJECT_CONTINUITY_PLAN.md](compliance/PROJECT_CONTINUITY_PLAN.md).
