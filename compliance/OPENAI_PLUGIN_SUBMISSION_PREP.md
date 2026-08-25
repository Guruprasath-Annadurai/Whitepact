# WhitePact — OpenAI Plugin Directory Submission Prep

> Everything in this document is content-only prep work — none of it required
> logging into any external account. What's *not* here (identity
> verification, domain verification, demo credentials) is called out at the
> bottom as the remaining founder-only steps. Format follows OpenAI's actual
> current submission form fields (`developers.openai.com/plugins/deploy/submission`,
> checked live 2026-08-13), not a guess.

---

## 1. Listing details

| Field | Value |
|---|---|
| Plugin name | WhitePact |
| Short description | AI governance MCP server — trust scoring, guardrails, hallucination/bias detection, and NIST AI RMF / EU AI Act / ISO 42001 compliance checks for any LLM agent. |
| Long description | WhitePact gives any LLM agent runtime AI-governance controls: PII/harm scanning, composite trust scoring across six dimensions, hallucination and bias evaluation, red-team payload generation, and compliance checks against major frameworks (NIST AI RMF, EU AI Act, ISO 42001). All 30 tools are read-only, non-destructive, and operate purely on caller-supplied input — no external network calls, no state mutation from the MCP layer itself. Self-hosted (stdio, free, MIT-licensed) or hosted (HTTP/SSE, Bearer-key authenticated). |
| Category | Developer Tools / AI Safety & Compliance (whichever single category the form allows — pick Developer Tools if forced to choose one) |
| Website | https://github.com/Guruprasath-Annadurai/Whitepact |
| Support URL | *(use whatever real support contact exists today — a GitHub Issues link is honest and functional: https://github.com/Guruprasath-Annadurai/Whitepact/issues)* |
| Privacy policy URL | **Blocked** — `PRIVACY_POLICY.md` is explicitly marked draft/not-attorney-reviewed. Do not submit until this is resolved; see §4. |
| Terms URL | **Blocked** — same as above, `TERMS_OF_SERVICE.md`. |

---

## 2. Starter prompts

Realistic prompts a ChatGPT user would type that map cleanly to a tool:

1. "Scan this text for PII before I send it to a customer: [text]"
2. "Give this model response a trust score across fairness, privacy, and security."
3. "Check if this AI system description would be high-risk under the EU AI Act."
4. "Evaluate this response for hallucination against the source context."
5. "Generate a compliance gap report for ISO 42001 based on our current controls."

---

## 3. Test cases

### Positive (5)

**1. PII scan**
- User prompt: *"Scan this for PII: 'Contact John at john@example.com or 555-123-4567.'"*
- Expected tool: `rai_scan`
- Expected result shape: JSON with `is_blocked`, `has_pii: true`, findings listing email + phone, and a redacted copy of the input text.
- Fixture data: none required — self-contained input, no auth needed beyond the standard Bearer key.

**2. Trust score**
- User prompt: *"Compute a trust score with fairness 0.8, privacy 0.9, security 0.7, robustness 0.85, compliance 0.9, authenticity 0.95."*
- Expected tool: `rai_trust_score`
- Expected result shape: JSON with numeric `score` (0-100) *and* `trust_score` (identical value,
  the field's original/stable name), `grade` (A-F), `risk_tier` (LOW/MEDIUM/HIGH/CRITICAL) *and*
  `risk` (identical value, the field's original/stable name).
  **Corrected 2026-08-25**: this document originally named only `score`/`risk_tier`, which did
  not match the tool's actual, tested output field names (`trust_score`/`risk` — see
  `tests/test_mcp_server.py`). `mcp/tools.py`'s `_handle_trust_score` now additively returns
  both names side by side; this was a genuine, reproducible documentation/implementation
  contract mismatch, not merely a prep-doc typo, and is a plausible contributor to a reviewer
  or ChatGPT expecting the literal field name `score`/`risk_tier` seeing something it didn't
  recognize.
- Fixture data: none — all inputs are user-supplied numbers.

**3. EU AI Act classification**
- User prompt: *"Classify this AI system under the EU AI Act: an automated resume-screening tool used for hiring decisions."*
- Expected tool: `rai_eu_ai_act_classify`
- Expected result shape: JSON with a risk category (e.g. `high_risk`) and the specific Annex/Article reasoning.
- Fixture data: none.

**4. Hallucination check**
- User prompt: *"Check this response for hallucination: source says 'the meeting is Tuesday,' response says 'the meeting is Wednesday.'"*
- Expected tool: `rai_hallucination`
- Expected result shape: JSON with `hallucination_detected: true`, `hallucination_risk` (0-1),
  `risk_level`, and `source_contradiction_detected: true`.
- Fixture data: none, but the prompt must be split into separate `text` (the response: "the
  meeting is Wednesday") and `source` (the reference: "the meeting is Tuesday") arguments for
  the tool to detect the disagreement — see the tool's schema/description for this split.
  **Corrected 2026-08-25**: run verbatim against the pre-2026-08-25 tool (no `source` argument
  existed, and the detector has no source-comparison capability at all — it only scores
  hedging language, cross-candidate self-consistency, and citation-pattern "unsupported
  claims"), this exact submitted test case produced `risk_level: "low"`, `hallucination_risk:
  0.2` — the **opposite** of the documented expected result. This is a confirmed, empirically
  reproduced test-case failure, not a hypothesis: verified locally by running the detector
  against this exact input before any fix was applied. Fixed by adding a bounded,
  general-purpose (not test-specific) day-of-week/month/number contradiction check plus an
  additive `hallucination_detected` field to `mcp/tools.py`'s `_handle_hallucination`.

**5. Org status — CONFIRMED CONTRACT MISMATCH, corrected 2026-08-25**
- Original prompt/expectation (as submitted 2026-08-13): *"What's the current status of my
  WhitePact organization?"* → `rai_org_status` → JSON with org id, plan tier, usage/quota
  summary, requiring a demo API key tied to a demo org.
- **This does not match what the tool actually does, and never did.** `rai_org_status` has no
  org id parameter, no auth/database lookup, and no connection whatsoever to a real org's
  plan/billing/usage records — every one of its fields (`model_grades`, `active_frameworks`,
  `open_incidents`, `budget_pct_used`, `drift_alerts`) is caller-supplied, and all are
  optional. Calling it with no arguments (exactly what "what's my org's status" with no
  supplied data would produce) returns a rollup of all-default/empty values — a fabricated,
  misleadingly clean "HEALTHY" status, not the real org's state. **This is the single highest-
  confidence, most severe finding of the 2026-08-25 hardening pass** — if OpenAI's reviewer
  ran this exact submitted case, there is no code path by which it could have produced the
  documented result, demo credentials or not.
- **Corrected test case** (what the tool can honestly do today): User prompt: *"Here's our
  current governance snapshot — models graded gpt-4o:A, claude:B, 2 open incidents, 45% of
  budget used, active frameworks NIST_AI_RMF — summarize our status."* → `rai_org_status` →
  JSON with `health_status`, `models.grade_distribution`, `operations.budget_status`, etc.,
  all derived from the supplied numbers.
- **Not fixed in this pass** (real, separate, larger work): wiring `rai_org_status` to the
  authenticated caller's real `OrgContext`/`OrgRepository` state on the hosted MCP transport
  (the `_current_org` ContextVar already carries `org_id`/`plan` at dispatch time — ADR-adjacent
  work, but requires deciding what a self-hosted stdio caller with no org context sees, and a
  security review of what's safe to expose per-org). Flagged as a recommended follow-up, not
  attempted here to avoid scope creep into an unrelated architecture change.

### Negative (3)

**1. Destructive action request**
- Scenario: *"Delete all my incident logs."*
- Expected behavior: refusal/clarification — no tool in the 30-tool surface performs deletion; the model should explain no such capability exists rather than attempting a workaround.
- Why it shouldn't complete: there is no delete/mutate tool exposed by this MCP server by design (all 30 tools are `readOnlyHint=true`, `destructiveHint=false`).

**2. Out-of-scope request**
- Scenario: *"Use this to generate marketing copy for our product."*
- Expected behavior: safe fallback — the model should recognize WhitePact's tools are governance/compliance-scoped and decline to force-fit an unrelated task onto them.
- Why it shouldn't complete: no tool in the surface performs general content generation; every tool has a narrow, named governance purpose.

**3. Missing required input**
- Scenario: *"Give me a trust score."* (no dimension values supplied)
- Expected behavior: clarification request — the model should ask for the six trust dimension values (fairness, privacy, security, robustness, compliance, authenticity) rather than calling the tool with fabricated defaults.
- Why it shouldn't complete as-is: `rai_trust_score`'s schema defaults missing dimensions to `0.5`, which would produce a misleadingly neutral score if the caller didn't actually mean to supply one — a reviewer testing this should see the model surface that ambiguity, not silently proceed.

---

## 4. What's still founder-only (cannot be prepped further from here)

- **Developer identity verification** in the OpenAI Platform Dashboard — needs your login.
- **Domain verification**: the portal generates a token at submission time to place at `whitepact-mcp-http.onrender.com/.well-known/openai-apps-challenge` — the route can only be built once the real token exists (starting the submission flow generates it).
- **Demo API key / demo org**: `rai_org_status`'s positive test case needs a real key a reviewer can use without MFA/SMS/email confirmation. Creating this means adding a new org record to the live production database — I can do this via the existing signup flow if you want, but it's a real persistent record on your live system, so I'm holding it for your go-ahead rather than doing it unprompted.
- **Privacy policy + terms**: both currently draft-only per their own stated caveats (§1) — this is the same blocker flagged for the Claude submission, now confirmed to block OpenAI too.
- **Availability (countries/regions)**: a business decision, not a technical one — no existing doc states a position on this.

## 5. Release notes draft

> Initial submission. WhitePact is an AI governance MCP server (30 tools,
> 10 canonical resources) providing trust scoring, guardrails, bias and
> hallucination detection, and compliance checks (NIST AI RMF, EU AI Act,
> ISO 42001) for any LLM agent. All tools are read-only and non-destructive
> by design — verified against the actual tool implementations, not
> asserted. MIT-licensed, self-hostable, with a hosted HTTP+SSE option
> available. No prior submitted version.
