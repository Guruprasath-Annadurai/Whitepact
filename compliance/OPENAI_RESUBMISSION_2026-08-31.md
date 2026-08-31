# WhitePact — OpenAI re-submission checklist (2026-08-31)

This is the current re-submission handoff for WhitePact after the 2026-08-25 OpenAI review rejection. It does not claim that OpenAI has approved, endorsed, or re-listed WhitePact.

## Why a re-submission is needed

The submitted WhitePact v1.2.3 app was rejected because one or more submitted test cases did not produce the documented expected results. OpenAI instructed the submitter to re-run all submitted test cases, align tool behavior/output with the expected outcomes, verify consistency on ChatGPT web and mobile, and then re-submit.

The repository subsequently fixed concrete review-contract mismatches in `eb64e1c8123bc017309f32ddcf6e57b69f59ac19` and the authenticated organization-status path in `84aa6506dabd0056cf1b2b874a9e9eb09f158fb0`.

## Version/count to use for a new submission

- Repository package version on `main`: **1.2.6** (`pyproject.toml`)
- Current MCP source-of-truth count: **30 tools / 20 advertised resources**
- MCP server identity: `whitepact`

Do not copy the stale README heading `Available tools (27)` into the submission. The current server has three later tools beyond that old table: `rai_memory_write_check`, `rai_memory_read_check`, and `rai_causal_influence_check`.

## Positive review tests to re-run

Run these as user-level ChatGPT prompts and record the actual selected tool and returned result. The final expected-output wording in the submission must match the observed current response, not an older document.

### P1 — PII scan

Prompt:

> Scan this for PII: Contact John at john@example.com or 555-123-4567.

Expected routing: `rai_scan`.

Acceptance check: the result identifies PII including the email/phone and provides the tool's current redacted/result structure. Do not hard-code field names into the submission until the current hosted response is observed.

### P2 — Trust score

Prompt:

> Compute a trust score with fairness 0.8, privacy 0.9, security 0.7, robustness 0.85, compliance 0.9, authenticity 0.95.

Expected routing: `rai_trust_score`.

Acceptance check: current code is intended to return the stable names `trust_score` / `risk` and the additive aliases `score` / `risk_tier`, with matching paired values. Confirm this against the hosted endpoint before re-submission.

### P3 — EU AI Act classification

Prompt:

> Classify this AI system under the EU AI Act: an automated resume-screening tool used for hiring decisions.

Expected routing: `rai_eu_ai_act_classify`, not the general maturity-assessment `rai_compliance` tool.

Acceptance check: result gives the tool's current risk classification and reasoning. Submit only the exact fields/terminology observed in the current response.

### P4 — Source contradiction / hallucination

Prompt:

> Check this response for hallucination: source says “the meeting is Tuesday,” response says “the meeting is Wednesday.”

Expected routing: `rai_hallucination` with the source and response split into the tool's separate `source` and `text` arguments.

Acceptance check: the current implementation should identify the source contradiction. Confirm the exact current output including `hallucination_detected` / contradiction fields before copying expected results into the form.

### P5 — Authenticated organization status

Run this only with a real demo/reviewer org and the exact auth mode that the submitted app will expose.

Prompt:

> What's the current status of my WhitePact organization?

Expected routing: `rai_org_status`.

Acceptance check on hosted authenticated transport: returned `org_id` and `plan` must match the real test organization, and usage fields must reflect that organization's actual MCP usage. Do not test this as if self-hosted stdio had an organization context; it intentionally does not.

## Negative review tests to re-run

### N1 — No delete capability

Prompt:

> Delete all my incident logs.

Acceptance check: ChatGPT must not invent a destructive WhitePact MCP capability. It should explain that the exposed WhitePact tool surface does not provide that deletion operation.

### N2 — Unrelated content-generation request

Prompt:

> Use WhitePact to generate marketing copy for our product.

Acceptance check: do not force an unrelated governance tool call. ChatGPT may answer normally outside WhitePact if the product allows it, but it must not falsely represent a WhitePact tool as a marketing-copy generator.

### N3 — Ambiguous trust-score request

Prompt:

> Give me a trust score.

Acceptance check: because the tool schema has defaults, this case needs special attention. The desired reviewer behavior is for ChatGPT to request the actual governance-dimension inputs rather than silently treating schema defaults as user-provided evidence. Verify actual ChatGPT web/mobile behavior before keeping this negative case in the submission. If ChatGPT legitimately calls the tool with defaults under current platform behavior, replace this test with a negative case whose expected behavior is deterministic rather than documenting an outcome the client does not produce.

## Critical re-submission checks

Before pressing Submit:

1. Run P1-P5 and N1-N3 in **ChatGPT web** using the same connector configuration/auth mode intended for review.
2. Run the same cases in **ChatGPT mobile** as requested in the rejection notice.
3. Record the actual tool selected and current response fields for each positive case.
4. Update submission expected results to those observed outputs; do not reuse stale v1.2.3 wording blindly.
5. Confirm `tools/list` exposes **30 tools** on the exact hosted endpoint used for review.
6. Confirm the hosted endpoint is not temporarily using an unsafe/demo authentication bypass after testing. The submission auth configuration and the deployed server must agree.
7. Confirm privacy-policy and terms URLs used in the form are the actual current public documents and that their status is acceptable for submission; do not imply attorney review if none occurred.
8. Use only official OpenSSF status: Best Practices **Silver** and OSPS Baseline **Level 1** unless those official records have changed.

## Claims to avoid in the app listing

Do not state or imply that WhitePact is OpenAI-approved before approval, enterprise-adopted, independently certified beyond the actual public badges, used by named companies without permission/evidence, or endorsed by OpenAI/Anthropic/Google/Microsoft/xAI merely because compatibility tests work.

## Founder-only handoff

The repository-side remediation and submission-copy preparation can be done without external account access. The remaining OpenAI actions are account-bound: connect the review endpoint in ChatGPT, run the exact web/mobile review matrix above, update any form fields whose observed outputs differ, and submit the new version through the authenticated OpenAI submission UI.
