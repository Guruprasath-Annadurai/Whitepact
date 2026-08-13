# WhitePact for Microsoft Copilot / Copilot Studio

**WhitePact — the authority layer for autonomous systems.**

WhitePact is an AI governance MCP server: trust scoring, PII/harmful
content guardrails, hallucination detection, and compliance checks
(NIST AI RMF, EU AI Act, ISO 42001) for any LLM agent — including agents
built and run in Copilot Studio.

## What it does for a Copilot agent

- Scans generated or retrieved text for PII and harmful content before it
  reaches a user (`rai_scan`).
- Scores claims for factual trustworthiness (`rai_trust_score`,
  `rai_hallucination`).
- Evaluates a proposed action against configurable policy rules and
  returns an ALLOW/DENY/REQUIRE_APPROVAL decision with an evidence
  record (`rai_policy_check`).
- Produces compliance gap reports against EU AI Act and ISO 42001
  (`rai_eu_ai_act_classify`, `rai_iso42001_gap`).

All 27 tools are read-only against the calling agent's own state — none
of them mutate the agent's environment. WhitePact evaluates and reports;
it does not act.

## Integration model

WhitePact runs as an external MCP server. A Copilot Studio agent (or a
Microsoft-certified connector, once submitted) reaches it over Streamable
HTTP with a Bearer API key — no code embedded in Copilot itself, no
platform-specific governance logic. See
`docs/integrations/microsoft-copilot.md` for the technical setup and
`docs/integrations/PLATFORM_COMPATIBILITY.md` for verified status.

## Status of this package

This is a **preparation package**, not a submission. Nothing here has
been submitted to Microsoft. See `FOUNDER_SUBMISSION_CHECKLIST.md` in
this directory for what still requires the founder.
