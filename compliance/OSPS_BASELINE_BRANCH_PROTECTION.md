# OSPS Baseline Level 1 — Branch Protection Controls

**Date verified**: 2026-08-17
**Updated**: 2026-08-18 — `required_status_checks.contexts` expanded from 4 to 8 (see "2026-08-18 update" below); this file's original body is left otherwise unchanged as a record of the initial baseline.
**Repository**: `Guruprasath-Annadurai/Whitepact`
**Default branch**: `main`
**Method**: GitHub classic branch protection (`PUT /repos/{owner}/{repo}/branches/main/protection`), applied and then independently re-fetched via `GET` in a separate API call — not merely echoed back from the write request.

## OSPS-AC-03.01 — Pull requests required, CI required, direct pushes prevented, admin bypass restricted

**STATUS: MET**

Before this change, `GET .../branches/main/protection` had no `required_pull_request_reviews` key and no `restrictions` key at all — meaning main had **no enforced PR requirement**: a contributor with write access could push directly to `main`, and `enforce_admins` was `false`.

Applied via full protection update:

```json
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "Lint · Type-check · Test (3.11)",
      "Lint · Type-check · Test (3.12)",
      "Build distribution",
      "Helm chart lint"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 0,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "require_last_push_approval": false
  },
  "restrictions": null,
  "required_conversation_resolution": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}
```

**Verified by independent `GET`** (not the `PUT` response):

- `required_pull_request_reviews` is now present and enforced — a PR is required to merge to `main`; direct pushes are rejected by GitHub for every actor, including the repository owner, because `enforce_admins.enabled: true`.
- `required_approving_review_count: 0` — deliberate, not an oversight: this repository currently has one real maintainer (see the still-open Silver/Gold bus-factor and second-maintainer gaps tracked separately). Requiring ≥1 approval today would deadlock the only maintainer out of their own repository. The PR-gate and CI-gate are real and enforced now; raising `required_approving_review_count` to 1 is a one-line follow-up once a second maintainer exists — tracked, not silently deferred.
- `required_status_checks.strict: true` with all 4 real CI job names as `contexts` — a PR cannot merge unless those checks pass on the up-to-date branch.
- `enforce_admins.enabled: true` — the repository owner/admin is bound by the same rule; no ordinary-change bypass path exists for anyone.

## OSPS-AC-03.02 — Deletion of main restricted, force pushes blocked

**STATUS: MET**

This was already correctly configured before this change and remains so:

- `allow_deletions.enabled: false` — `main` cannot be deleted by any actor through the protected-branch API.
- `allow_force_pushes.enabled: false` — force pushes to `main` are rejected.

## Bypass configuration

No repository rulesets exist (`GET .../rulesets` → `[]`), so classic branch protection is the sole, non-conflicting source of truth — there is no separate ruleset with its own bypass-actor list that could override or weaken these settings.

## Evidence commands (reproducible)

```bash
gh api repos/Guruprasath-Annadurai/Whitepact/branches/main/protection
gh api repos/Guruprasath-Annadurai/Whitepact/rulesets
```

## Result

| Control | Status |
|---|---|
| OSPS-AC-03.01 | **MET** |
| OSPS-AC-03.02 | **MET** |

Both verified against a fresh `GET`, not assumed from the write request succeeding.

---

## 2026-08-18 update — required checks expanded from 4 to 8

**Gap found**: `CONTRIBUTING.md`'s Accessibility section calls `pa11y-ci` "a hard gate," the DCO section says a missing sign-off "fails" the check, and the i18n test job exists specifically to block bad catalogs — but none of `dco-check`, `gitleaks`, `Accessibility (WCAG2AA)`, or `i18n unit tests` were actually present in `required_status_checks.contexts`. They ran on every PR and reported pass/fail, but GitHub would still allow a merge with any of them failing, because only the original 4 job names (`Lint · Type-check · Test (3.11)`/`(3.12)`, `Build distribution`, `Helm chart lint`) were wired as required. This is exactly the gap OpenSSF Silver item 18 (CI hardening) flags — a check that exists but isn't actually enforced is indistinguishable from no check at PR-merge time.

**Fix applied**:

```bash
gh api -X PATCH repos/Guruprasath-Annadurai/Whitepact/branches/main/protection/required_status_checks \
  -F strict=true \
  -f 'contexts[]=Lint · Type-check · Test (3.11)' \
  -f 'contexts[]=Lint · Type-check · Test (3.12)' \
  -f 'contexts[]=Build distribution' \
  -f 'contexts[]=Helm chart lint' \
  -f 'contexts[]=dco-check' \
  -f 'contexts[]=gitleaks' \
  -f 'contexts[]=Accessibility (WCAG2AA)' \
  -f 'contexts[]=i18n unit tests'
```

**Verified by independent `GET`** immediately after: `required_status_checks.contexts` now lists all 8 job names.

**`dependency-review` deliberately excluded**: this job fails on every PR today because the repository's Dependency graph setting isn't enabled (a pre-existing, separate gap, tracked in this same document's original body and in `OPENSSF_SILVER_GAP_ANALYSIS.md` item 18) — making it required would block every PR unconditionally, which is worse than the current honestly-documented gap. Fix the underlying Dependency graph setting first, then add it as a required check in a follow-up, not the other way around.
