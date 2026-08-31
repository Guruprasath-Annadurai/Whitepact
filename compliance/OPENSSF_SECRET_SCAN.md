# OpenSSF `no_leaked_credentials` — Secret Scan Report

## Current validation addendum — 2026-08-31

Gitleaks v8.30.1 scanned all 423 reachable commits and approximately 10.19 MB
with redaction enabled. One new scanner hit was reviewed: historical commit
`22f67d5`, `tests/test_saml.py:252`, where a negative signature test passes an
RSA private key generated in memory to the SAML signer. The repository contains
the variable reference, not key material or a credential. Its exact historical
fingerprint is documented in `.gitleaksignore`; no rule-wide suppression was
added. After that narrow false-positive classification, the full-history scan
reports zero unignored leaks.

The dated report below is retained as evidence of the earlier scan and
out-of-repository credential incident. Its counts describe the 2026-08-17 run,
not the current repository history.

**Date**: 2026-08-17
**Scanner**: [gitleaks](https://github.com/gitleaks/gitleaks) v8.30.1 — full git history
**Second scanner**: TruffleHog — **NOT RUN** (not installed in this environment; not attempted with a fabricated or partial result). If independent corroboration is required, run `trufflehog git file://. --since-commit=<root>` before this document is treated as final on that point.

## Scope

- `gitleaks git --log-opts="--all"` — every reachable commit across every branch/tag in this repository's history, not just `HEAD`. **294 commits scanned, ~6.84 MB.**
- Working tree (implicitly covered — the working tree's current state is the tip of the scanned history).
- Not separately scanned as distinct targets (see limitations): GitHub Actions run logs (as opposed to workflow *files*, which are in-repo and covered), and any external system (Render/Supabase/GitHub secrets stores) — those are runtime credential stores, not something a git-history scanner reads.

## Findings

**12 total gitleaks hits, all in documentation, all placeholders — zero real credentials.**

| # | File | Rule | Match (redacted context) | Classification |
|---|---|---|---|---|
| 1-4, 5-8 | `wiki/Authentication-and-RBAC.md` (2 commits, same content) | `curl-auth-header` | `Bearer your-key-here`, `Bearer owner-key` (×3) | **PLACEHOLDER** |
| 9, 12 | `DEPLOYMENT.md` (2 commits, same content) | `curl-auth-header` | `Bearer abc123def456...` | **PLACEHOLDER** |
| 10, 11 | `DEPLOYMENT.md` (2 commits, same content) | `generic-api-key` | `RAI_API_KEYS=abc123def456...` | **PLACEHOLDER** |

Every match is a documentation example illustrating the *shape* of a curl command or env var, using an obviously-fake value (`your-key-here`, `owner-key`, `abc123def456...`) — none decode to, resemble, or could function as a real API key, database credential, or signing secret. No `REAL_ACTIVE_CREDENTIAL`, `REAL_REVOKED_CREDENTIAL`, or `TEST_FIXTURE` findings.

## A separate, real finding — outside git, not caught by this scan

**This is not a gitleaks finding** (a chat transcript and local shell history are not part of the git-scannable surface), but it is real and material to `no_leaked_credentials`'s intent, so it is recorded here rather than omitted:

During this session's live-production debugging (a database-migration incident on the hosted `responsibleai-dashboard` service), the founder pasted the **production Supabase Postgres connection string, including its plaintext password**, directly into the chat session, multiple times, and it was also typed directly into the founder's local shell (landing in `~/.zsh_history`).

- **Type**: Supabase/Postgres database password (pooler connection string).
- **Location**: chat session transcript; local shell history on the founder's machine. **Not** committed to git, **not** present in any file in this repository.
- **Status, updated 2026-08-17 (later same day)**: the founder rotated the Supabase database password and reported it done. **Independently verified by this session, not merely trusted**: attempted a direct connection using the exact old, previously-exposed password — rejected with `InvalidPasswordError: password authentication failed for user "postgres"`. The old credential is confirmed dead.

This finding is called out explicitly per the instruction that no valid credential exposure be omitted from this report merely because it falls outside the specific tool's scan surface — and closed only once independently verified, not merely claimed.

## Remediation status

| Finding class | Status |
|---|---|
| Git-history placeholder secrets (12 gitleaks hits) | No action needed — confirmed non-functional placeholders, not real credentials. |
| Production DB password pasted into chat/shell (this session) | **RESOLVED, verified.** Password rotated; old credential independently confirmed rejected (`InvalidPasswordError`) by this session, not just taken on the founder's word. |

## Limitations, stated plainly

- TruffleHog was not run (not installed in this environment). Gitleaks' full-history scan is the sole automated coverage this report can attest to.
- This scan covers the git-reachable history of this repository only. It does not cover: secrets that may exist in external systems (Render/Supabase/GitHub environment variable stores), secrets in this session's chat transcript (addressed manually above, not by tooling), or secrets in any fork/mirror of this repository outside GitHub's own record.
- A clean scan proves no *currently git-reachable* commit contains a detected credential — it does not prove no credential was ever briefly present and then force-pushed away (gitleaks scans reachable history; a genuinely unreachable, garbage-collected commit would not be found by this or any git-history scanner without access to GitHub's own reflog/audit systems, which this session does not have).

## Final result

**No valid credential remains exposed.** Git history was clean from the start. The one real, live credential exposure identified during this audit (outside git — this session's own chat/shell activity) has been resolved: the founder rotated it, and this session independently confirmed the old password no longer authenticates. `no_leaked_credentials` is closed.
