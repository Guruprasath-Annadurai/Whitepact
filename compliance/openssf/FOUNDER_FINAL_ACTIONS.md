# Founder Final Actions — OpenSSF Readiness

**Date:** 2026-08-29
Short list. Only things structurally requiring the repository owner — nothing here could have been done by this engineering pass instead.

1. **Recruit a real second maintainer** with standing access and real project knowledge. Blocks Silver items 6–7, Gold `bus_factor`, Gold `contributors_unassociated`, and (transitively) `two_person_review` and raising `required_approving_review_count` above 0.

2. **Confirm account-level 2FA** (TOTP/hardware key/passkey, not SMS) on the GitHub account maintaining this repo, and be prepared to attest to it. Blocks Gold `require_2FA`/`secure_2FA` — no repository file can prove this.

3. **Check live security headers on `whitepact.com`** (`curl -sI https://whitepact.com` or securityheaders.com) to confirm CSP/HSTS/X-Content-Type-Options/X-Frame-Options are actually served, not just coded in `middleware.py`. Blocks Gold `hardened_site`. Likely already true; genuinely unverified this session for lack of network access.

4. **Enable the "Dependency graph" repository setting** (Settings → Code security and analysis) so `.github/workflows/dependency-review.yml` stops failing on every PR and can become a required status check. A GitHub UI toggle, five minutes.

5. **Decide whether to merge PR #52** (`security/openssf-hardening`) into `main`. It contains real, ready hardening (Action SHA pinning, Dependabot, token-permission scoping, reproducible-build gate, `docs/CODE_REVIEW.md`) that this pass deliberately did not duplicate or merge. Merging it directly improves several Scorecard checks (Pinned-Dependencies, Token-Permissions, Dependency-Update-Tool) at zero new engineering cost.

6. **Submit the OpenSSF Best Practices Silver web form** at bestpractices.dev/projects/14112 once ready — several fields are currently unanswered on the live form independent of the underlying repository evidence (`compliance/OPENSSF_SILVER_GAP_ANALYSIS.md`). This is an account-tied manual step; no automation can submit it.

That's the complete list. Everything else in this readiness pass — per-file SPDX headers, hard CI coverage gates, workflow hardening, Scorecard sub-checks — is real engineering/process work this pass either did, or explicitly deferred as a scoped follow-up (see `OPENSSF_HARDENING_REPORT.md`), not owner-only work.
