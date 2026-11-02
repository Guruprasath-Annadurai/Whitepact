# WhitePact Trust Index

WhitePact is an open-source AI governance platform. This connector exposes its free, public Trust Index API — score any AI model or tool against a six-dimension trust standard (fairness, privacy, security, robustness, compliance, authenticity), verify a previously issued score, or check whether a model has a known trust rating and reported incidents on file.

## Publisher: Guruprasath Annadurai

## Prerequisites

None. All operations in this connector are public, free, and unauthenticated — no WhitePact account, API key, or license is required.

## Supported Operations

### Check service health

Returns the live health and version of the WhitePact service. Useful as a connectivity test before running other actions.

### Self-assess a model or tool

Score any AI model or tool across six trust dimensions and receive a durable, independently-verifiable Trust Passport with a `passport_id` and a `verify_url`. Self-assessed scores are always returned with `certified: false` — this endpoint never claims third-party review.

### Verify a Trust Passport

Look up a previously issued Trust Passport by ID. Lets anyone check that a cited trust score is real, not just an unfalsifiable claim in marketing copy.

### Check a model's known trust score

Given a model name and provider, returns whether a Trust Index assessment is on file, the score if known, and whether any incidents have been publicly reported against that model/provider.

### Browse the Trust Index registry

Paginated list of every assessed model/tool, certified and self-reported alike, newest first.

## Obtaining Credentials

None needed. Every operation in this connector calls WhitePact's public, unauthenticated endpoints.

## Getting Started

Add the "Check a model's known trust score" action to a Flow with a hardcoded model name and provider (for example `gpt-4` / `openai`) to see a working response with zero setup.

## Known Issues and Limitations

- The registry and check endpoints are rate-limited (60–120 requests/minute) to keep the free tier usable for everyone; a Flow that calls these in a tight loop may be throttled.
- Self-assessed Trust Passports are exactly that — self-reported. The connector always surfaces the `certified` field so a Flow or downstream logic can distinguish self-reported scores from human-reviewed ones; treat `certified: false` results accordingly.
- This connector covers the free, public subset of WhitePact's API. Org-scoped features (RBAC, billing, audit log, incident reporting) are intentionally out of scope for an unauthenticated Independent Publisher connector and are documented separately at https://github.com/Guruprasath-Annadurai/Whitepact.

## Frequently Asked Questions

### Is this the same as WhitePact's MCP server?

No. WhitePact also ships a 27-tool MCP server for AI agents (documented at https://github.com/Guruprasath-Annadurai/Whitepact/blob/main/docs/integrations/PLATFORM_COMPATIBILITY.md). This connector exposes a small, unauthenticated slice of the same backend as a standard Power Platform/Copilot Studio connector, for use in Flows and Copilot Studio agents that don't speak MCP directly.

### Does self-assessing cost anything?

No — self-assessment is free and requires no signup, by design, so the trust standard stays usable by anyone.
