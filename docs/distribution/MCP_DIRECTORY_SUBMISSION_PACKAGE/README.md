# MCP directory submission package (DRAFT, NOT SUBMITTED)

Assessed 2026-10-11. Nothing here has been submitted, uploaded or published. Each directory's current rules must be
re-read before use (`WHITEPACT_GLOBAL_DISTRIBUTION_READINESS_REPORT.md`).

## Listing metadata (truthful, for the developer-evaluation release)

* **Name:** WhitePact
* **One line (≤100 chars, registry limit):** Runtime authority for AI agent tool calls: authorize, approve, revoke, audit. Stdio is advisory.
* **Long description:** WhitePact is an open-source runtime authority layer for AI agents. Hosted deployments
  authorize tool calls against organization policy and delegated authority, hold high-risk actions for a human
  approver, run approved tools in an isolated container, and keep a hash-chained evidence record. **This MCP
  server's advertised tools are read-only analysis tools** (guardrail scans, trust and compliance scoring, policy
  checks, memory-authority checks). The local stdio server is **advisory and does not enforce anything on code
  that does not call it**. Trust scoring, bias, hallucination and deepfake analysis are heuristic or experimental.
  Not certified; no independent penetration test is claimed.
* **Repository / license:** https://github.com/Guruprasath-Annadurai/Whitepact, MIT
* **Transports:** Streamable HTTP (`/mcp`, stateless), legacy HTTP+SSE (`/sse`), stdio (local)
* **Authentication:** Bearer API key; OAuth 2.0 authorization-code + PKCE (S256) for reviewer logins with RFC 9728
  protected-resource metadata (scope `whitepact:review`). API keys are not OAuth.
* **Support / security contact:** `SECURITY.md` (private advisory form, maintainer email). **Privacy policy:** `PRIVACY_POLICY.md`
  (must be served from the owned domain). **Terms:** `TERMS_OF_SERVICE.md`.
* **Maturity statement to show reviewers:** developer-evaluation candidate; enterprise production is NO-GO.

## Example prompts (at least three working examples are required by Anthropic; OpenAI asks for starter prompts)

1. "Scan this text for personal data and tell me what would be redacted: …" → `rai_scan`
2. "Does this agent memory write look like an injection attempt? …" → `rai_memory_write_check`
3. "Classify this system under the EU AI Act: an automated resume-screening tool used by employers." → `rai_eu_ai_act_classify`
4. "Check whether a response is supported by this source text." → `rai_hallucination` (heuristic)

## Reviewer instructions (to be completed by the founder)

A demo organization with hosted entitlement and sample data, a reviewer OAuth client, and a login that does not
require 2FA on an inaccessible device are required by both programmes. **None exists yet.** Do not use production
credentials. The reviewer flow is covered by `tests/test_mcp_oauth_authorization_server.py` (30 tests).

## Advertised tools (generated from `TOOL_DEFS`; the internal test fixture is never listed)

| # | Tool | Title | readOnly | destructive | openWorld | idempotent |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `rai_scan` | Scan for PII & Harmful Content | True | False | False | True |
| 2 | `rai_trust_score` | Compute AI Trust Score | True | False | False | True |
| 3 | `rai_compliance` | Evaluate Governance Compliance | True | False | False | True |
| 4 | `rai_hallucination` | Detect Hallucination Risk | True | False | False | True |
| 5 | `rai_cost_estimate` | Estimate Model API Cost | True | False | False | True |
| 6 | `rai_redteam_payloads` | Get Red Team Attack Payloads | True | False | False | True |
| 7 | `rai_redteam_analyze` | Analyze Red Team Responses | True | False | False | True |
| 8 | `rai_compare_models` | Compare Two Models' Trust Scores | True | False | False | True |
| 9 | `rai_audit_summary` | Get Governance Capability Summary | True | False | False | True |
| 10 | `rai_health` | Check Governance Engine Health | True | False | False | True |
| 11 | `rai_bias_evaluate` | Evaluate Demographic Bias | True | False | False | True |
| 12 | `rai_drift_check` | Check Trust Score Drift | True | False | False | True |
| 13 | `rai_passport_generate` | Generate AI Passport | True | False | False | True |
| 14 | `rai_budget_check` | Check AI Spending Against Budget | True | False | False | True |
| 15 | `rai_policy_check` | Check Text Against Governance Policy | True | False | False | True |
| 16 | `rai_stream_scan` | Scan Streaming Text Chunks | True | False | False | True |
| 17 | `rai_benchmark` | Evaluate Responses Against Benchmark | True | False | False | True |
| 18 | `rai_benchmark_prompts` | Get Benchmark Question Set | True | False | False | True |
| 19 | `rai_model_route` | Recommend Optimal Model | True | False | False | True |
| 20 | `rai_pii_report` | Generate PII Audit Report | True | False | False | True |
| 21 | `rai_incident_log` | Build Governance Incident Record | True | False | False | True |
| 22 | `rai_eu_ai_act_classify` | Classify EU AI Act Risk Tier | True | False | False | True |
| 23 | `rai_iso42001_gap` | Run ISO 42001 Gap Analysis | True | False | False | True |
| 24 | `rai_executive_summary` | Generate Executive Governance Summary | True | False | False | True |
| 25 | `rai_org_status` | Get Organization Governance Status | True | False | False | True |
| 26 | `rai_check_trust` | Check Public Trust Index Score | True | False | False | True |
| 27 | `rai_webhook_status` | Check Webhook Delivery Health | True | False | False | True |
| 28 | `rai_memory_write_check` | Check Memory Write for Injection Patterns | True | False | False | True |
| 29 | `rai_memory_read_check` | Check Memory Read Scope Authorization | True | False | False | True |
| 30 | `rai_causal_influence_check` | Check Causal Influence Provenance for Injection Patterns | True | False | False | True |

All 30 are annotated `readOnlyHint=true`, `destructiveHint=false`, `openWorldHint=false`. That is accurate: none writes
external state. `rai_incident_log` builds an incident record and states that it stores nothing.

## What the directories would not yet find

The product's core (authority decisions, approvals, revocation, evidence) is **not** exposed through this tool
list. A reviewer would find a scoring toolkit. Options, none implemented:

* **A. Submit as is**, described honestly as an analysis toolkit with a hosted governance backend. Smallest change;
  weakest fit with the product's purpose.
* **B. Add narrow, tenant-scoped, read-only authority tools**: `whitepact_policy_status` (policy version, rule
  summary, history head and chain validity), `whitepact_simulate_policy` (first matching rule for an action type
  and target; policy only, authority not evaluated), `whitepact_list_pending_approvals` (metadata only, no
  arguments), `whitepact_verify_evidence` (chain status for the organization). They read the control plane's own
  database after authentication and role checks. **They would not run inside the isolated tool executor**, which
  has no database access by design, so they are a new read path. That is a security-boundary decision (and
  adds ~4 tools to every manifest and test), so it is left for a decision rather than built.
* **C. Plugin with skills only**, no MCP, for the open-source stdio package.

## Hard blockers (not engineering)

Owned MCP hostname and DNS; developer identity verification; reviewer tenant and credentials; legal review of
privacy and terms; founder authorization for every submission.
