# Current assurance baseline (evidence snapshot)

**Captured:** 2026-09-22 (pre–Combined V1 RC)  
**Purpose:** Record current OpenSSF / OSPS state before badge answers are changed.  
**Do not** treat this file as an official badge submission.

## Sources

| Program | Version / source | Official state (BadgeApp) |
|---------|------------------|---------------------------|
| OpenSSF Best Practices | [criteria](https://www.bestpractices.dev/criteria) via project **14112** | **Passing + Silver** earned; **Gold not earned** |
| OSPS Baseline | **2026.08.28** checklist | **Level 1 awarded**; L2/L3 self-audit in `OSPS_BASELINE_CURRENT_AUDIT.md` |
| OpenSSF Scorecard | action **v2.4.4** | Last `main` run **success** @ `b6044b9` (2026-09-18) |

## Criterion matrix (abbreviated)

| Criterion | Current answer | Evidence | Blocker type | Fixable now |
|-----------|----------------|----------|--------------|-------------|
| Gold `bus_factor` | Unmet | One primary maintainer | **human/org** | NO |
| Gold `contributors_unassociated` | Unmet | 2 GitHub contributors API; not 2 *significant unassociated* | **human/org** | NO |
| Gold `two_person_review` | Unmet / low % | Solo maintainer history | **human/historical** | Process only for future |
| Gold `require_2FA` / `secure_2FA` | Unknown in repo | Account setting | **human** | NO (owner) |
| Gold `test_statement_coverage90` | Met on `main` CI | `OPENSSF_GOLD_GAP_ANALYSIS.md`, CI run 33198911431 | — | YES (maintain) |
| Gold `test_branch_coverage80` | Met on `main` CI | same | — | YES (maintain) |
| Gold `copyright_per_file` / `license_per_file` | Technically ready | `manage_license_headers.py`, openssf-policy workflow | refresh BadgeApp | YES |
| Gold `reproducible_build` | Partial evidence | `reproducible-build.yml`; byte-identical not proven this pass | **technical** | Investigate on branch |
| Gold `security_review` | Self-review documented | `THREAT_MODEL.md`, compliance reviews | independent review optional | Partial |
| OSPS L2 signing/manifest | Partial | Lane D draft scripts; no final signed release | **human/release** | Prepare only |
| OSPS L3 maturity | Not awarded | BadgeApp 0% L3 at last audit | **maturity** | MATURITY_ELIGIBILITY_PENDING |
| P0 test tool on RC | Fixed in #102 / `8df07ff` | `test_mcp_production_tool_registry.py` | — | YES |
| Live v1.2.6 MCP | No test tool in card | external probe 2026-09-22 | — | N/A |
| MCPBeat uptime | Unresolved | `docs/release/MCPBEAT_INVESTIGATION.md` | **mixed** | No auth bypass |

## PR disposition (engineering review)

| PR | Verdict (this pass) |
|----|---------------------|
| #102 | **READY_TO_MERGE** (human merge to RC) |
| #100 | **NEEDS_FIX** on `main` alone — metadata used `len(TOOL_DEFS)`; superseded fixes on assurance branch |
| #101 | **SAFE_FOR_LATER_RC_INTEGRATION** (non-P0 health/docs) |
| #91 | **NEEDS_FIX** — superseded README hero on assurance branch |
| #86 | **DEFER_TO_COMBINED_RC** — CONFLICTING, superseded by current assurance lanes |

## GitHub settings (observable / required actions)

| Setting | Action |
|---------|--------|
| Default workflow `read` permissions | **GITHUB_SETTING_ACTION_REQUIRED** if not already org default |
| Branch protection on `main` | Verify required checks include CI + openssf-policy |
| Private vulnerability reporting | Enable if not already |
| 2FA on org/account | **HUMAN_ACTION_REQUIRED** |

## Review history (honest)

| Metric | Value |
|--------|-------|
| TOTAL_RELEVANT_CHANGES | Not fully measured this pass |
| REVIEWED_BY_OTHER_HUMAN | Below Gold 50% threshold (solo maintainer) |
| MEASURED_PERCENTAGE | **FAIL** vs Gold `two_person_review` |
| Remediation | Require second reviewer on future PRs; cannot rewrite history |

## Contributor independence

| Metric | Value |
|--------|-------|
| CURRENT_SIGNIFICANT_CONTRIBUTORS | Primarily 1 maintainer (+ bots/dependabot) |
| UNASSOCIATED_COUNT | **FAIL** Gold threshold |
| Classification | **GOLD_ORGANIZATIONAL_BLOCKER** |
