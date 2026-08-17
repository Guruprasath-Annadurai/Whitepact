# OpenSSF `no_leaked_credentials` — Secret Scan Report

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
- **Status as of this document**: rotation was recommended twice during that session. **Not independently verified as completed** — this document cannot confirm rotation without the founder confirming it, and no confirmation was given before this report was written.
- **Action required**: rotate the Supabase database password (Supabase dashboard → Database → Settings → Database Password → Reset), then update the `RAI_DATABASE_URL` environment variable on the `responsibleai-dashboard` Render service to match, if not already done.

This finding is called out explicitly per the instruction that no valid credential exposure be omitted from this report merely because it falls outside the specific tool's scan surface.

## Remediation status

| Finding class | Status |
|---|---|
| Git-history placeholder secrets (12 gitleaks hits) | No action needed — confirmed non-functional placeholders, not real credentials. |
| Production DB password pasted into chat/shell (this session) | **ROTATION REQUIRED, not confirmed complete.** See above. |

## Limitations, stated plainly

- TruffleHog was not run (not installed in this environment). Gitleaks' full-history scan is the sole automated coverage this report can attest to.
- This scan covers the git-reachable history of this repository only. It does not cover: secrets that may exist in external systems (Render/Supabase/GitHub environment variable stores), secrets in this session's chat transcript (addressed manually above, not by tooling), or secrets in any fork/mirror of this repository outside GitHub's own record.
- A clean scan proves no *currently git-reachable* commit contains a detected credential — it does not prove no credential was ever briefly present and then force-pushed away (gitleaks scans reachable history; a genuinely unreachable, garbage-collected commit would not be found by this or any git-history scanner without access to GitHub's own reflog/audit systems, which this session does not have).

## Final result

**No valid, git-committed credential was found exposed in this repository's history.** The one real, live credential exposure identified during this audit occurred outside git (this session's own chat/shell activity) and requires the founder's confirmation that rotation has been completed before this criterion can be called fully closed.
