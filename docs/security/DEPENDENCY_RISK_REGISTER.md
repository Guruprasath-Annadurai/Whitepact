# Dependency Risk Register

**Directive**: WHITEPACT — FULL ENTERPRISE PRODUCTION + PUBLIC LAUNCH
CLOSURE MASTER DIRECTIVE, Phase 10. Formally records the one open
dependency finding this repository carries, instead of leaving it as a
chat-history investigation with no owner or review date.

**Scope**: this document tracks *known, currently-open* dependency
findings that were investigated and deliberately not fixed (because no
fix exists, or the finding doesn't apply to this codebase's actual
usage), so the decision is durable and reviewable — not a general
changelog of every dependency bump. Automated scanning already covers
day-to-day dependency hygiene: `pip-audit` (CI, Python), `npm audit`
(informally, no dedicated CI job today — see "Gaps" below), Dependabot
(both ecosystems), `dependency-review` (PR-proposed changes),
CodeQL, and OpenSSF Scorecard — see `.github/workflows/*.yml`.

---

## Open findings

### 1. `extract-zip` — symlink path traversal (CVE-2026-56876)

| Field | Value |
|---|---|
| **Severity** | HIGH (npm/GitHub advisory rating) |
| **Affected package** | `extract-zip` (all versions — no patched release exists) |
| **Dependency path** | `pa11y-ci` → `puppeteer`/`puppeteer-core` → `@puppeteer/browsers` → `extract-zip` |
| **Where it's used** | `package.json`'s single `devDependencies` entry (`pa11y-ci`), used only by CI accessibility-scan tooling — never shipped, never installed in any production image or runtime dependency of the `responsibleai` Python package. |
| **What the vulnerability requires** | The advisory describes a symlink-based path-traversal triggerable when `extract-zip` extracts an **attacker-controlled** zip archive. |
| **Why it doesn't apply here** | The only zip `extract-zip` ever extracts in this codebase's actual usage is Puppeteer's own trusted Chromium browser download, fetched by `@puppeteer/browsers` directly from Google's official CDN over HTTPS during CI setup — never a user-supplied or externally-submitted archive. This repository has no code path that hands `extract-zip` an untrusted file. |
| **Fix availability** | None. Confirmed by dry-running `npm audit fix --force` and inspecting every version in the chain (`extract-zip` 2.0.1 is the latest npm release and is still listed as vulnerable; no newer release exists upstream as of this review). Re-confirmed via a fresh `npm audit --json` run on this date (see "Verification" below) — same 6 findings, same root cause, unchanged. |
| **Compensating control** | CI-only exposure surface; the workflow that runs `pa11y-ci` does not process any external/attacker-supplied input through the zip-extraction path — it only extracts Puppeteer's own pinned Chromium build. |
| **Disposition** | **Accepted risk, recorded formally.** Recommended action communicated to the repo owner: dismiss the Dependabot alert with this documented rationale (not unilaterally dismissed by this session — the repo owner's call). |
| **Owner** | Repository owner (`Guruprasath-Annadurai`) — dismissal/acceptance of the Dependabot alert itself requires repo-admin action this session does not have permission to take. |
| **Review date** | Re-check at the next `pa11y-ci`/`puppeteer` major-version bump, or 2027-03-01, whichever comes first — a new upstream `extract-zip` release closing the underlying CVE would allow this line to be removed entirely rather than re-justified. |
| **First identified** | This session, during the Heart Production Closure initiative (see `docs/heart-production-closure/CHATGPT_HANDOFF_SUMMARY.md`). |
| **Last re-verified** | This session, Phase 10 (see "Verification" below) — finding is unchanged. |

---

## Verification

Re-run fresh for this register, not quoted from memory:

```
$ npm audit --json | jq '.metadata.vulnerabilities'
{"info": 0, "low": 0, "moderate": 0, "high": 6, "critical": 0, "total": 6}
```

All 6 are the same `extract-zip` dependency chain (`extract-zip`,
`@puppeteer/browsers`, `puppeteer`, `puppeteer-core`, `pa11y`,
`pa11y-ci`) — one root cause, one finding above, not six independent
ones.

```
$ pip-audit -r <(pip freeze)
No known vulnerabilities found
```

Python dependencies (the actual shipped `responsibleai` package and
its runtime requirements) carry **zero** currently-known
vulnerabilities as of this review.

## Gaps this register surfaces (process, not vulnerability, findings)

- **No dedicated `npm audit` CI job.** Python has `pip-audit` wired
  into CI (`.github/workflows/ci.yml`); the `package.json` devDependency
  tree (CI-only tooling) has no equivalent scheduled scan — Dependabot
  alerts are the only automated signal today. Low priority given the
  devDependency-only, CI-only exposure, but worth a future CI job for
  parity and to avoid this register going stale silently.
- **GitHub Actions pinning** — not verified by this document (see
  `00_MASTER_READINESS_AUDIT.md`'s Supply-chain row, deferred to a
  later phase): whether workflow `uses:` lines are pinned to a full
  commit SHA vs. a mutable version tag.

## Maintenance

Update this register whenever:
- A new dependency finding is investigated and deliberately not fixed
  (add a new row with the same fields).
- An existing finding's fix becomes available upstream (close the row,
  note the resolving version and date).
- The stated review date arrives (re-verify, update "Last re-verified",
  and either re-confirm the disposition or escalate).

Do not use this document as a substitute for actually applying
available fixes — it exists specifically for findings where no
current fix exists or the finding doesn't apply, which is the only
case a "risk register" entry (as opposed to a dependency bump) is the
correct response.
