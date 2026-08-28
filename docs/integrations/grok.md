# xAI Grok

**Status**: VERIFIED (Path B, xAI API) — see `PLATFORM_COMPATIBILITY.md`.
**Source-of-truth date**: 2026-08-14.

Two independent paths exist. They reach the same WhitePact endpoint and
tools; pick whichever fits your workflow.

## Path B — xAI API remote MCP (VERIFIED live 2026-08-14)

See [`../../examples/grok/remote_mcp_example.py`](../../examples/grok/remote_mcp_example.py).
Reads `XAI_API_KEY` and `WHITEPACT_API_KEY` from the environment only —
never hardcode them. The example scopes `allowed_tools` to a small
read-only set rather than enabling all 27 tools by default.

```bash
export XAI_API_KEY=...        # your own key, not committed anywhere
export WHITEPACT_API_KEY=...  # your own key
python examples/grok/remote_mcp_example.py
```

**Run live end-to-end 2026-08-14** with real credentials: Grok connected
to the hosted WhitePact MCP server, authenticated, discovered `rai_scan`,
and called it — a genuine full round trip (connect → auth → discover →
call → structured response), not a config check. The response was
WhitePact's own correct plan-gating logic (`hosted_access_unavailable`,
since the test org is on the FREE plan, which has zero hosted-access
quota by design) — expected behavior, not a bug. Two real bugs were
found and fixed getting here:

1. `"Failed to connect to MCP server"` — traced to a mixed-up
   `WHITEPACT_API_KEY` (an OWNER-role dashboard key doesn't authenticate
   against the MCP server; needs a proper org-scoped key from
   `POST /api/orgs/{id}/keys`).
2. The bearer token belongs in a dedicated `authorization` field on the
   OpenAI SDK's `Mcp` tool type, not stuffed into `headers` — confirmed
   from the real installed SDK's type definitions.

## Path A — Grok custom connector (grok.com) — private, not a directory listing

1. `grok.com/connectors` → **New Connector** → **Custom**.
2. URL: `https://YOUR_WHITEPACT_HOST/mcp` (verified candidate deployment).
3. Authentication: Bearer token, value = your WhitePact API key.

Not exercised — requires an interactive grok.com session. **Important:**
per xAI's own docs, a custom connector added this way is visible only to
the account (or, for Business/Enterprise, the org) that added it — it
does **not** make WhitePact discoverable to other Grok users. This is a
bring-your-own config, not a listing.

## Making WhitePact publicly discoverable on xAI's platforms

Researched live 2026-08-14, two distinct xAI product surfaces, don't
conflate them:

- **`grok.com`'s connector catalog** (the ~30-connector list at
  `grok.com/connectors`) is curated and maintained by xAI itself. No
  public submission process was found — getting listed here likely
  requires a direct partnership/outreach relationship with xAI, not a
  self-serve form. Not attempted.
- **`xai-org/plugin-marketplace`** — a real, official, **open,
  PR-based submission process**, confirmed by reading the repo's own
  `README.md` and `CONTRIBUTING.md` directly. This is the catalog for
  **Grok Build** (xAI's terminal coding agent), a different product from
  the `grok.com` chat connectors above. A plugin here can bundle an
  `.mcp.json` pointing at a hosted MCP server — WhitePact fits this
  exactly. Submission is a 6-step PR process (fork, add an entry to
  `.grok-plugin/marketplace.json` under `external_plugins/`, pin a full
  commit SHA if using a remote source, regenerate the index, validate
  locally, open the PR for CI + code-owner review). This would make
  WhitePact discoverable to **Grok Build developers**, not general
  `grok.com` chat users — a real but narrower audience than the main
  connector catalog.
- The community repo `github.com/rdmgator12/awesome-grok-connectors` is
  an unofficial third-party list (same pattern as the Mistral one found
  earlier) — low-value, zero-cost discoverability, not a real xAI
  channel.

## Safe test prompt

> "Call whitepact's rai_scan on: 'SSN 123-45-6789, call me at 555-0100.'"

Expected on a FREE-plan test org: `hosted_access_unavailable`, correctly
labeled, per the live-verified run above. On a paid-plan key: PII
findings for SSN and phone, redacted copy returned.

## Common errors

| Symptom | Cause | Fix |
|---|---|---|
| `401` | Bad/missing Bearer key | Re-check `WHITEPACT_API_KEY` |
| `"Failed to connect to MCP server"` | Wrong key (dashboard OWNER key instead of an org-scoped key) — confirmed live 2026-08-14 | Create a key via `POST /api/orgs/{id}/keys`, use its `raw_key`, not the dashboard's `RAI_API_KEY` |
| `hosted_access_unavailable` in the tool response | Org is on the FREE plan (zero hosted quota by design) | Upgrade the org's plan, or use `stdio` self-hosted transport instead (always free) |
| Empty tool list | `allowed_tools` misconfigured to an empty set | Widen the allowlist, verify tool names against `rai_*` prefix |

## Security notes

`allowed_tools` is used deliberately in the example to avoid handing a
new integration blanket access on day one — expand it once the connector
is confirmed working. Two real secrets were exposed during live testing
of this integration (a dashboard OWNER key, and later a scoped WhitePact
key visible in an SDK response repr) — both were flagged as compromised
and rotation was required; treat any credential that appears in a
terminal paste or a library's object repr as burned.

## Founder action

- Path A: create the connector in `grok.com/connectors` yourself if you
  want it for your own personal use (private, not a listing).
- Public discoverability: decide whether to pursue the
  `xai-org/plugin-marketplace` PR (Grok Build audience) and/or outreach
  to xAI for the main `grok.com/connectors` catalog (no self-serve path
  found for that one).
- To exercise the full data-returning path (not just the plan-gated
  response already verified): upgrade the test org's plan.
