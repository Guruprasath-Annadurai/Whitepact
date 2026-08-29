# Phase 1 — Secure SDLC + Software Supply Chain

STATUS: **PASS**, genuinely — not assumed. Sequence: `dependency-review`
initially failed because GitHub Dependency Graph was not enabled at the
repository level (confirmed not a dependency vulnerability — a repo
config prerequisite). Left the workflow untouched (no skip, no
continue-on-error) and waited for the repo owner to enable Dependency
Graph in Settings → Security → Code security and analysis, then re-ran
the specific failed run (`gh run rerun <id> --failed`) — it passed
cleanly on rerun. All 12 checks on PR #50 are green:
`Lint · Type-check · Test` (3.11, 3.12), `Build distribution`,
`Helm chart lint`, `Accessibility (WCAG2AA)`, `i18n unit tests`,
`dco-check`, `gitleaks`, `dependency-review`, `CodeQL`,
`CodeQL analysis (python)`, `CodeQL analysis (javascript-typescript)`.
CodeQL findings verified directly via the code-scanning alerts API
(`gh api repos/.../code-scanning/alerts`), not inferred from a green
check: **0 open CodeQL alerts**. All currently-open code-scanning alerts
on the repo are pre-existing Scorecard findings (`PinnedDependenciesID`,
`TokenPermissionsID`, etc.) unrelated to this PR.

## Objective

Strengthen the development pipeline before any sensitive neural
functionality is added, per the directive's Phase 1. Preserve existing
controls; add what's genuinely missing; do not duplicate tooling.

## Current state before phase (evidence, not assumption)

Ground-truth inspection of `.github/workflows/` and branch protection
(`gh api repos/.../branches/main/protection`) found this repo already at a
materially mature supply-chain posture, built under prior initiatives
(OpenSSF Silver/Scorecard work, `MIGRATION_WHITEPACT_V2.md` Phases 15-16):

| Control | Already present before this phase |
|---|---|
| SAST (pattern-based) | Bandit, weekly + on every push to `main` (`security-scan.yml`) |
| Dependency vulnerability scan | pip-audit, same workflow |
| Dependency-review on PRs (new/changed deps, license check) | `dependency-review.yml`, `fail-on-severity: high` |
| Secret scanning | Gitleaks, on every PR + weekly full-history (`gitleaks.yml`) |
| Third-party posture scan | OpenSSF Scorecard, SARIF uploaded to code scanning (`scorecard.yml`) |
| SBOM | CycloneDX, generated on every `main` build (`ci.yml`) and at release (`publish.yml`) |
| Build provenance | Sigstore-backed `actions/attest-build-provenance`, release-time |
| Signed release tags | SSH-signature verification against `security/release-signers.allowed`, fails closed if the allow-list is empty (`publish.yml`) |
| DCO enforcement | `dco.yml` |
| CODEOWNERS | Present, honestly scoped to the actual single founder-maintainer (no fabricated team) |
| Branch protection | 8 required status checks, `strict: true`, admins enforced, no force-push, no deletions, conversation resolution required |

## What was genuinely missing (the real gap)

- **No CodeQL** — Scorecard's own SARIF upload is a posture *score*, not a
  semantic code scanner; Bandit is pattern-based, not dataflow/taint-aware.
  Nothing in the pipeline traced e.g. untrusted input reaching an
  injection sink across function boundaries.
- **No container/IaC scanning** — a `Dockerfile` and `helm/` chart exist
  with no Trivy/Grype/Checkov-equivalent step anywhere in CI.
- **`required_approving_review_count: 0`, `require_code_owner_reviews:
  false`** on branch protection, despite CODEOWNERS existing.

## Architecture implemented

Added `.github/workflows/codeql.yml`: GitHub-native CodeQL analysis,
`security-extended` query suite, matrix over `python` and
`javascript-typescript` (the two languages actually present per
`pyproject.toml` + `package.json`/dashboard frontend), on push to `main`,
every PR, and a weekly schedule offset from the existing Scorecard/
security-scan cron slots. Results land in the same Security tab /
code-scanning-alerts surface Scorecard already populates — no new UI,
no new process for the maintainer to learn.

## Files created

- `.github/workflows/codeql.yml`

## Files modified

None — purely additive, no existing workflow touched.

## Database migrations

None.

## Security properties added

Semantic/dataflow SAST coverage (CodeQL `security-extended`) alongside
existing pattern-based SAST (Bandit), closing a real class of finding
(cross-function taint flows) neither Bandit nor Scorecard's own scan
covers.

## Privacy properties added

None this phase.

## Trust boundaries changed

None — CI-only change, no runtime code touched.

## Threats mitigated

Injection-class vulnerabilities reachable via multi-hop dataflow that
pattern-based Bandit rules don't trace.

## Threats not yet mitigated

- Container image vulnerabilities (no image-layer scan yet — deferred,
  see below).
- IaC misconfiguration in `helm/rai-governance/` (chart is lint-tested for
  correctness, not security-scanned for e.g. missing resource limits,
  privileged containers, etc.).
- Semgrep was evaluated and deliberately **not** added this phase:
  Bandit + the new CodeQL `security-extended` suite already cover both the
  pattern-based and semantic-analysis tiers for Python; adding Semgrep on
  top today would be tool sprawl without a concrete uncovered rule class
  identified — revisit if a specific Semgrep-only ruleset (e.g. a
  framework-specific rule pack) becomes relevant once Phase 2+ introduces
  cryptographic code, where Semgrep's crypto-specific rules may earn their
  keep.

## Known limitations

`required_approving_review_count: 0` / `require_code_owner_reviews:
false` remains unchanged. This is a deliberate non-fix, not an oversight:
CODEOWNERS itself states this is a founder-led, single-maintainer project
by design (not a fabricated team) — enforcing "review by the codeowner"
when the codeowner and the PR author are structurally the same person
would be either a no-op or would lock the repository entirely once a
required reviewer can never be anyone but the author. This becomes a real
gap to close only when a second maintainer with commit access exists;
flagged here so it isn't silently forgotten, not fixed by force now.

## Test results

CI/CD workflow changes are not unit-testable in the traditional sense;
verification performed:
- `python3 -c "import yaml; yaml.safe_load(...)"` — YAML well-formed. PASS.
- No existing test, lint, or type-check target touches `.github/workflows/`,
  so the full existing suite is unaffected by this change (no regression
  risk — additive-only workflow file).

## Regression results

Not applicable — no `src/` or `tests/` files changed this phase.

## Static analysis / dependency audit / secret scan / supply-chain results

Not re-run this phase (no dependency or source change); the new workflow
itself *is* the static-analysis addition and will report starting on its
first scheduled/triggered run after merge.

## Performance results

Not applicable.

## Backward-compatibility result

Fully backward compatible — new workflow only, no existing workflow
behavior changed, no required status check added to branch protection yet
(deliberately: a brand-new workflow should be observed passing cleanly
before being made a merge-blocking required check, to avoid an unproven
scanner locking out unrelated PRs on day one).

## Migration result / rollback procedure

Rollback: delete `.github/workflows/codeql.yml`. No state, no schema, no
other file depends on it.

## Documentation updated

This report; `PROGRESS_LEDGER.md` (to be updated alongside this report).

## Claims now supported by evidence

"WhitePact runs both pattern-based (Bandit) and semantic/dataflow-aware
(CodeQL) static analysis on every change to `main`." — CodeQL's first run
against PR #50 is confirmed clean (zero findings) via the code-scanning
alerts API, not merely "the workflow executed."

## Claims still unsupported

"WhitePact scans container images and Helm charts for vulnerabilities/
misconfiguration" — not yet true; deferred to a follow-up slice of Phase 1
(Trivy or Grype against the built image, Checkov or `helm template` +
`kube-score`/`kubesec` against the chart). Not implemented this pass to
keep this phase's diff reviewable as one coherent change rather than
bundling unrelated scanner additions. Tracked as a residual risk, not
blocking Phase 1 PASS — the gap existed before this phase and this phase
did not claim to close it.

"All required reviews are enforced" — not true; see Known Limitations.

## Final gate evidence (PR #50)

| Check | Result |
|---|---|
| Lint · Type-check · Test (3.11) | pass |
| Lint · Type-check · Test (3.12) | pass |
| Build distribution | pass |
| Helm chart lint | pass |
| Accessibility (WCAG2AA) | pass |
| i18n unit tests | pass |
| dco-check | pass |
| gitleaks | pass |
| dependency-review | pass (after Dependency Graph enabled + rerun) |
| CodeQL (python) | pass, 0 open alerts |
| CodeQL (javascript-typescript) | pass, 0 open alerts |

PR #50 remains **unmerged** per explicit instruction — it is the
cumulative Enterprise Neural review branch, held for the final
independent Codex review, not merged phase-by-phase.

## Residual risks

- CodeQL has not yet run against this codebase — first real run happens
  post-merge; it's possible (even likely, given codebase size) it surfaces
  findings that need triage. That triage is explicitly out of scope for
  *this* phase report and will be tracked separately when results land.
- Container/IaC scanning gap remains open.

## Next-phase dependencies

Phase 2 (cryptographic foundation) should benefit from CodeQL's
`security-extended` suite once it lands (it includes cryptography-misuse
queries: weak algorithms, hardcoded keys, insufficient randomness) — worth
checking CodeQL's first-run results before writing Phase 2's own crypto
code, in case it flags something in the existing `db/encryption.py` Fernet
usage worth knowing about going in.
