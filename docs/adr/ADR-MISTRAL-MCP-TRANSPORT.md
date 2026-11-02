# ADR: Transport strategy for Mistral Le Chat compatibility

**Status**: Accepted (Option A, revisit if Mistral publishes a confirmed
SSE-only requirement).
**Date**: 2026-08-13.

## Context

The task of onboarding WhitePact to Mistral Le Chat requires knowing what
transport Le Chat's MCP client actually requires. Two claims exist from
research this project has done:

1. Mistral operates tiered connector systems (Featured Connectors, a
   curated MCP Connectors directory, and bring-your-own custom MCP) —
   found via web search, not from an official Mistral document read
   directly.
2. A PR-based submission flow (canonical vendor URL, surface type,
   category, use case) was found, but it lives in
   `github.com/rdmgator12/awesome-mistral-connectors` — a third-party
   community "awesome list," not a repository Mistral owns or operates.
   **No official Mistral-run submission channel was confirmed.**

Neither source stated definitively whether Le Chat's MCP client requires
legacy HTTP+SSE, Streamable HTTP, or accepts both. Because that fact
could not be confirmed from an authoritative source, this ADR does not
assume SSE-only and does not restore or expand legacy transport support
on the strength of an unverified claim.

WhitePact currently serves **both** Streamable HTTP (`/mcp`, primary) and
legacy SSE (`/sse`, still live) — see `MIGRATION_WHITEPACT_V2.md` Section
on transport modernization. So even in the worst case (Le Chat requires
SSE only), WhitePact already supports it today without any new code.

## Options considered

**Option A — Retain Streamable HTTP + existing legacy SSE, no new work.**
WhitePact already serves both. If Le Chat needs SSE, `.../sse` already
exists. If Le Chat needs Streamable HTTP, `.../mcp` already exists. This
requires zero engineering effort and adds zero new attack surface.

**Option B — Build a small compatibility proxy/adapter.**
Only relevant if Le Chat required a transport WhitePact doesn't serve at
all (e.g. WebSocket-only, or a Mistral-proprietary variant). No evidence
found that this is the case. Rejected as unjustified speculative work.

**Option C — Actively re-invest in legacy SSE (e.g. un-deprecate it,
document it as first-class, build new tooling around it).**
Rejected. SSE is already served for backward compatibility, but treating
it as first-class going forward increases long-term maintenance and
attack surface for a transport the MCP ecosystem is moving away from,
without a confirmed requirement forcing that investment.

## Decision

**Option A.** No new transport work. WhitePact's existing dual-transport
support (Streamable HTTP primary, SSE legacy) already covers every
plausible Le Chat requirement without introducing new legacy protocol
investment. Nothing is restored, nothing is removed.

## Why this satisfies the "no new legacy transport unless justified"
default

The default from the task brief is: don't reintroduce legacy transports
without justification. This ADR doesn't reintroduce anything — SSE was
never removed — so the default is honored by inaction, not by an
exception.

## Status marker

Per `PLATFORM_COMPATIBILITY.md`, Mistral is marked:

```
BLOCKED_BY_CLIENT_TRANSPORT
```

This reflects that the *submission channel*, not the transport, is the
actual blocker: WhitePact's transport already covers both possibilities,
but there is no confirmed official channel to submit to. If Mistral
publishes an official submission process, re-evaluate this ADR only if
that process states a transport requirement WhitePact does not already
serve — which, per the above, is unlikely.

## Founder action

Confirm directly with Mistral (developer relations contact, official
docs, or a real account on their platform) what their actual MCP
Connectors directory submission process is, since no confirmed official
channel exists in current research. See `docs/integrations/FOUNDER_ACTIONS.md`.
