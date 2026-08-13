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
| Long description | WhitePact gives any LLM agent runtime AI-governance controls: PII/harm scanning, composite trust scoring across six dimensions, hallucination and bias evaluation, red-team payload generation, and compliance checks against major frameworks (NIST AI RMF, EU AI Act, ISO 42001). All 27 tools are read-only, non-destructive, and operate purely on caller-supplied input — no external network calls, no state mutation from the MCP layer itself. Self-hosted (stdio, free, MIT-licensed) or hosted (HTTP/SSE, Bearer-key authenticated). |
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
- Expected result shape: JSON with numeric `score` (0-100), `grade` (A-F), `risk_tier` (LOW/MEDIUM/HIGH/CRITICAL).
- Fixture data: none — all inputs are user-supplied numbers.

**3. EU AI Act classification**
- User prompt: *"Classify this AI system under the EU AI Act: an automated resume-screening tool used for hiring decisions."*
- Expected tool: `rai_eu_ai_act_classify`
- Expected result shape: JSON with a risk category (e.g. `high_risk`) and the specific Annex/Article reasoning.
- Fixture data: none.

**4. Hallucination check**
- User prompt: *"Check this response for hallucination: source says 'the meeting is Tuesday,' response says 'the meeting is Wednesday.'"*
- Expected tool: `rai_hallucination`
- Expected result shape: JSON with `hallucination_detected: true` and a confidence/explanation field.
- Fixture data: none.

**5. Org status**
- User prompt: *"What's the current status of my WhitePact organization?"*
- Expected tool: `rai_org_status`
- Expected result shape: JSON with org id, plan tier, usage/quota summary.
- Fixture data: **requires a real demo API key tied to a demo org** — this is the one positive case that needs founder-provisioned demo credentials (see §4).

### Negative (3)

**1. Destructive action request**
- Scenario: *"Delete all my incident logs."*
- Expected behavior: refusal/clarification — no tool in the 27-tool surface performs deletion; the model should explain no such capability exists rather than attempting a workaround.
- Why it shouldn't complete: there is no delete/mutate tool exposed by this MCP server by design (all 27 tools are `readOnlyHint=true`, `destructiveHint=false`).

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

> Initial submission. WhitePact is an AI governance MCP server (27 tools,
> 10 canonical resources) providing trust scoring, guardrails, bias and
> hallucination detection, and compliance checks (NIST AI RMF, EU AI Act,
> ISO 42001) for any LLM agent. All tools are read-only and non-destructive
> by design — verified against the actual tool implementations, not
> asserted. MIT-licensed, self-hostable, with a hosted HTTP+SSE option
> available. No prior submitted version.
