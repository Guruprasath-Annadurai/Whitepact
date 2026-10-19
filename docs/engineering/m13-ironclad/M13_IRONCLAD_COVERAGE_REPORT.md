# IRONCLAD coverage

Final qualification update (2026-10-19): frozen implementation HEAD `ccf4e8cc80f1de52a0a9b445298055ac581f53e1`, tree `c7bef348b9dcea2e55a86d4b01f357fb1498ecd2`, parent `47fc55a1591890f18c06333b4f187d091535719d`. Draft PR #221 targets `codex/whitepact-m13-absolute-convergence`. Evidence-only branch adds tests/reports; implementation equivalence is checked independently. The current results below supersede historical pending statements retained later in this audit trail. M13 OPEN. GLOBAL PRODUCTION NO-GO.

## Current exact-source evidence

Completed exact-source full [39243226832](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39243226832): **8029 unique cases each,7928 PASS/67 FAIL/0 ERROR/34 SKIP each**, complete accounting, eight shards per interpreter. Python3.11 branch **6949/8618=80.63355767%**, statements30693/33726=91.0069%; Python3.12 branch **6974/8618=80.92364818%**, statements30738/33726=91.1404%. Same source scopes and80% branch threshold; no old/targeted coverage merged. Coverage gate PASS; overall matrix FAIL (tests/Ruff). Source growth changes denominator from8604 to8618; comparisons do not pretend unchanged denominator. All34 original environment skips remain SKIP. Separate exactcc actual localhost CrewAI/LlamaIndex runs **22 PASS per interpreter** (3.11 18.03s;3.12 18.74s) use real dependencies and no paid LLM; initial missing dependency collection/setup attempts are retained separately, not counted as passes. New evidence-only four-case probes are excluded from sourcecc coverage/accounting.

## Baseline and policy

Exact baseline `7939341f`: 7,950-case inventory per interpreter,8 shards each:3.11 statement90.1271%,branch6788/8604=78.8935%;3.12 statement90.2488%,branch6811/8604=79.1609%. Branch threshold 80% remains unchanged. At unchanged denominator need6884 covered branches (gaps96/73). No exclusions, narrowed source or merged stale coverage accepted.

Largest relevant missing arcs at `7939341f`: authority/service273,security/service76,security/router31,in_flight23,MCPserver17. New real signed authority mutation tests and policy-compatible counterparts target denial/rollback/tenant/identity invariants. Targeted coverage is diagnostic and does not substitute for a final independently accounted full8-shard/16-job run. New-head aggregate branch coverage NOT_EXECUTED yet.

Original per-version counts:3.11 7849 PASS66 FAIL1 ERROR34 SKIP;3.12 7850 PASS66 FAIL34 SKIP.34 skips comprise22 optional CrewAI/LlamaIndex,3 TerraformCLI,2 Bash3.2,1 shallowM5object,3 documentation environment/provider cases,1 covered async boundary,1 ACL/root-unavailable refusal inapplicable on privileged runner,1 unrequested benchmark. Original `7939341f` separate framework22 PASS each and Mac Bash3.2 twoPASS do not relabel original Linux skips. New-head separate qualification pending.

Full rerun deferred until actionable targeted changes settle. No usage-limit rejection observed; do not attribute NOT_EXECUTED to nonexistent quota evidence.

## New component evidence

Authority14-case run:14 PASS72.86 s; identity/capability11-case run:11 PASS67.08 s. Fresh local path-based branch coverage observed47 and95 previously missing exact793 authority/service arcs respectively using unchanged source-line endpoint mapping. Counts overlap and must not be summed. These are diagnostic comparisons only; no stale source coverage files were combined. New exact-head full-matrix aggregate is still required for both Python versions.

Additional negative upstream admission and observer scope:10 PASS6.60 s. A constructed candidate permit appears only in denial tests; it is not an actual customer ALLOW/grant/execution receipt. Genuine workspace ACTIVE+disabled-server yields stale-epoch denial, while SUSPENDED/DISABLED organization yields organization denial; all assert zero external dispatch. Original test omits the organization entirely, so organization-first denial correctly precedes its expected stale-epoch error.

## Deduplicated diagnostic arc comparison

Across the two genuine component runs, unchanged-endpoint mapping found138 unique old missing authority/service arcs relative to the Python3.11 baseline (47+95-overlap4); comparison against the Python3.12 baseline found139 (48+96-overlap5). **Both new local runs used Python3.11**; this is not Python3.12 execution evidence. The authority run's source was reconstructed from the recorded diff and matching coverage function boundaries because it lacked a contemporaneous source snapshot. No coverage files were merged. Exact committed-head full CI remains the sole threshold evidence.
