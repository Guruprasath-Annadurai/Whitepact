# Project Continuity Plan

**Date established**: 2026-08-18 (OpenSSF Silver `access_continuity` remediation —
see `compliance/OPENSSF_SILVER_GAP_ANALYSIS.md` item 5).

## Why this document exists, and what it does not fix

WhitePact has exactly one maintainer today (`GOVERNANCE.md` Section 2,
`.github/CODEOWNERS`). This document is the checklist of *what a second,
trusted person would need in order to keep the project running* if the
founder became unavailable — access points, recovery steps, a 7-day
plan. Writing this checklist does not create bus-factor redundancy by
itself: **no second person currently holds any of the access described
below.** That is a separate, standing gap
(`compliance/OPENSSF_SILVER_GAP_ANALYSIS.md` items 6–7, "founder action
required" — choosing and provisioning a real second person is not
something achievable by editing files in this repository). This
document exists so that when that person is chosen, activating them is
a matter of following a checklist, not improvising from scratch.

**No real credential, token, password, or secret value appears anywhere
in this document or in git.** Every item below names *where* the
credential lives and *who/what* can issue a new one, never the value
itself.

## Systems inventory and recovery path

| System | What it controls | Current holder | Recovery path if founder is unavailable |
|---|---|---|---|
| **GitHub** (`Guruprasath-Annadurai/Whitepact`) | Source code, Actions/CI, Releases, branch protection, `main` | Founder (sole org/repo owner) | GitHub's [account recovery](https://docs.github.com/en/authentication/troubleshooting-ssh/deleted-or-missing-ssh-keys) process for the owner account, or GitHub Support's documented process for regaining access to an organization when the sole owner is unreachable. A second person with no prior access has no faster path — this is why item 6/7 (granting real access to a second person *now*) matters more than any recovery procedure. |
| **Domain / DNS** (`whitepact.com`) | Where the domain resolves; MX/TXT records | Founder, at the domain registrar used to purchase `whitepact.com` | Registrar account recovery (registrar-specific — verify registrar-of-record and enable registry lock / transfer lock status is known before an incident, not during one). DNS provider (if separate from registrar) has its own recovery path. |
| **PyPI** (`rai-governance-platform`) | Publishing new package versions | Founder's PyPI account; publishing is via [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC from `.github/workflows/publish.yml`, no stored API token) — confirmed by reading that workflow, which uses `pypa/gh-action-pypi-publish@release/v1` with `id-token: write` and no `password`/token input | Trusted Publishing means PyPI releases are gated by GitHub Actions access to the `pypi` environment, not a separate PyPI credential — so GitHub recovery (above) is the actual dependency here. PyPI's own [account recovery](https://pypi.org/help/#account-recovery) process is the fallback if the PyPI account itself (not just publishing) needs to change hands. |
| **MCP Registry** (`io.github.Guruprasath-Annadurai/whitepact`, `server.json`) | The public MCP server listing | Founder's GitHub identity (registry auth is GitHub-OIDC-based, per the `io.github.*` namespace convention) | Tied to GitHub identity — see GitHub recovery above. No separate registry credential exists. |
| **Render** (`whitepact-mcp-http` service, dashboard hosting) | The live hosted instance at `whitepact.com` and `whitepact-mcp-http.onrender.com` | Founder's Render account | Render account recovery via Render support. **Gap**: no documented second Render account with admin/deploy access exists today — this is a real single point of failure for the *hosted* deployment specifically (self-hosted `pip install rai-governance-platform` deployments are unaffected). |
| **Database** (PostgreSQL, `RAI_DATABASE_URL`) | All persisted org/audit/trust/incident/governance data for the hosted instance | Whichever managed Postgres provider backs the Render deployment; connection string held in Render's environment config, not in git | Recovery depends entirely on the Render account above, plus the DB provider's own backup/point-in-time-recovery capability (verify this is enabled — not independently confirmed in this pass; flagged as an open action below). |
| **Redis** (`RAI_REDIS_URL`) | Shared rate-limit counters across dashboard instances | Same as database — provider-managed, connection string in Render env config | Non-critical for data durability (rate-limit state, not source-of-truth data) — a fresh Redis instance with an updated `RAI_REDIS_URL` is sufficient; no backup requirement. |
| **Security contact** (`annaduraiguruprasath7@gmail.com`, per `SECURITY.md`) | Where vulnerability reports arrive | Founder's personal email | No secondary/shared inbox exists today. If this address becomes unreachable, incoming reports have no fallback — a real gap, listed below. |
| **Release signing / provenance** | Build provenance attestation on published artifacts | GitHub Actions' `actions/attest-build-provenance@v2` (Sigstore-backed, keyless — tied to the workflow's OIDC identity, not a stored signing key) | No private key exists to lose or recover — provenance is generated fresh per release from GitHub Actions' own identity. Dependent entirely on GitHub repo access (above). |
| **Incident response** | Who is notified/acts when something goes wrong in production | Founder (per `GOVERNANCE.md` Section 2 — same person is maintainer, security contact, and incident commander) | No fallback exists — see `GOVERNANCE.md` Section 4's own statement that a self-review/self-response model is a known limitation until a real second person exists. |
| **Billing** (Render, domain registrar, any paid SaaS the project depends on) | Whether the hosted instance and domain stay live | Founder's payment method(s) | No documented secondary payment method or prepaid-runway buffer. If the founder's card lapses or account is inaccessible, the hosted instance and/or domain can go down with no automatic recovery. Flagged below. |

## 7-day recovery-objective checklist

If the founder became unexpectedly unavailable, here is the sequence a
trusted second person would need to follow, and by when, to keep
WhitePact minimally alive. These are targets to design toward, not
capabilities that exist today (see the "Known gaps" section — most of
these are currently blocked on nobody else having access yet).

1. **Day 0–1: Confirm what's actually at risk.** Check whether the
   hosted instance (`whitepact.com`) is still serving traffic and
   whether GitHub Actions (CI, and any scheduled/cron jobs) are still
   running. Neither requires any action by itself — Render and GitHub
   both keep running without day-to-day intervention as long as billing
   stays current and nobody revokes access.
2. **Day 1–3: Establish communication.** Post a visible notice (GitHub
   repo README banner, or a pinned issue) if the founder is
   confirmed unavailable for an extended period, so users/contributors
   aren't left guessing. Attempt GitHub's account-recovery or
   organization-transfer process if repo access is actually lost (not
   just the founder being slow to respond).
3. **Day 3–5: Secure billing continuity.** Confirm Render and the
   domain registrar's payment methods have enough runway (prepaid
   credit, or a secondary card) to avoid service interruption while
   longer-term access transfer is sorted out.
4. **Day 5–7: Establish a security-response fallback.** If the
   `SECURITY.md` contact address is genuinely unreachable, publish an
   interim reporting path (e.g., a GitHub Security Advisory draft, or a
   temporary alternate contact) so a live vulnerability report doesn't
   go unanswered indefinitely.
5. **Ongoing**: none of steps 1–4 require code changes or a release —
   they are entirely about access and communication. A release
   (patch, security fix) is only in scope once someone actually holds
   GitHub write access, which is the standing gap this whole document
   is downstream of.

## Known gaps (stated honestly, not smoothed over)

- **No second person holds any access described above.** This document
  is a checklist for when one exists, not evidence that continuity
  already works. Silver items 6 and 7 remain "founder action required"
  until this changes.
- **No secondary Render account, no secondary security-contact inbox,
  no documented secondary payment method.** Each of these is a single
  point of failure specific to the *hosted* deployment and the
  *founder's personal accounts* — the self-hosted, `pip install`-based
  path (source code, PyPI package, MCP stdio server) is unaffected by
  any of them, since it requires no ongoing infrastructure the founder
  personally operates.
- **Database backup/point-in-time-recovery status for the hosted
  Postgres instance was not independently verified while writing this
  document** — confirming this (and documenting the actual RPO/RTO the
  provider offers) is a real follow-up action, not assumed here.
- **This plan has never been drilled.** Per the verification method in
  `compliance/OPENSSF_SILVER_GAP_ANALYSIS.md` item 5, this plan is only
  actually proven once a second, independent person attempts it and
  confirms each listed capability is reachable. That hasn't happened
  yet, because no second person exists yet.

## Reporting an issue with this plan

If a step above turns out to be wrong, incomplete, or a system listed
here has since changed (registrar, hosting provider, etc.), open a
[GitHub issue](https://github.com/Guruprasath-Annadurai/Whitepact/issues)
— this document should track reality, not the state of the project on
the day it was written.
