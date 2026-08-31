# OpenSSF Hardening Report

**Branch:** `security/openssf-hardening`  
**Base:** `main`  
**Scope:** repository/supply-chain hardening and Best Practices evidence only; no WhitePact runtime feature logic changed.

## Changes in this branch

- Pinned external GitHub Actions to immutable 40-character commit SHAs.
- Reduced workflow token permissions, especially release publishing permissions.
- Added weekly Dependabot coverage for GitHub Actions, Python, and Docker dependencies.
- Pinned Docker base/service images to immutable multi-platform index digests while retaining readable tags.
- Added a CI policy guard that rejects future movable GitHub Action references.
- Added a detailed code-review/security-review standard.
- Added `.bestpractices.json` evidence proposals for OpenSSF Best Practices automation.
- Added an explicit Gold gap analysis that leaves human/organizational requirements Unmet rather than fabricating compliance.

## Current Best Practices position

WhitePact has already earned the Silver badge. Gold is **not** claimed by this branch.

Known Gold blockers include organizational requirements that repository changes cannot create:

- bus factor >= 2;
- at least two unassociated significant contributors; and
- sufficient two-person pre-release review history.

Known technical/evidence items still requiring a later dedicated pass include:

- consistent per-file copyright statements;
- consistent per-file SPDX license identifiers;
- exact proof of >=90% pure statement coverage;
- live project-site hardening-header verification; and
- account-level cryptographic 2FA evidence.

## Scorecard caveats

The earlier hardening branch pinned GitHub Actions and container images and reduced token
permissions. The later Scorecard hardening branch adds the coherent hash-locked Python
bootstrap/dependency workflow that this historical report identified as remaining work. See
`OPENSSF_SCORECARD_CURRENT.md` for the current evidence boundary; no post-change score is
claimed before an official rescan.

## Verification policy

This report does not claim the branch passes CI until GitHub Actions has executed against the branch/PR head. The pull request is the verification surface.
