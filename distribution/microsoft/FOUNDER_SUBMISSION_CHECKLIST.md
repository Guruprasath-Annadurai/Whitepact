# Microsoft Copilot certification — founder submission checklist

Nothing in the Mode 2 section below has been done. It lists exactly what
a Microsoft-certified (Mode 2) connector submission requires, so the
founder can decide whether it's worth pursuing, and do it without
re-deriving these requirements from scratch.

**Claude did not, and will not, do any of the following** — each needs an
account, a legal identity, a payment, or a UI confirmation only the
founder can provide.

## Mode 3 (Independent Publisher connector) — real, solo-developer path, files built

**Researched and confirmed 2026-08-16**: Microsoft's native "MCP server
certification (preview)" pipeline (Mode 2, below) requires a verified
publisher with a Microsoft Partner Center account and completed business
verification — confirmed directly from Microsoft's own docs, no
individual-developer exception. This remains blocked until Radtech LLP
is incorporated.

A separate, genuinely solo-developer-friendly path exists: the
**Independent Publisher Connector Group** — free, no business entity, no
Partner Center account, submitted via a GitHub pull request to
`microsoft/PowerPlatformConnectors`. It certifies a standard OpenAPI
2.0-based custom connector (not an MCP manifest directly), which becomes
available in Power Platform / Copilot Studio as a premium connector with
Microsoft's generic icon.

**Files built 2026-08-16**, covering 5 of WhitePact's real, public,
unauthenticated REST endpoints (health check, self-assess, verify,
check, registry — deliberately excludes org-scoped/RBAC/billing
endpoints, which are out of scope for an unauthenticated connector):

- `independent-publisher-connector/apiDefinition.swagger.json` —
  hand-authored Swagger 2.0 spec (validated with
  `openapi-spec-validator`), pointed at the live
  `responsibleai-dashboard.onrender.com` host
- `independent-publisher-connector/apiProperties.json` — required
  `iconBrandColor: "#da3b01"` per Independent Publisher rules
- `independent-publisher-connector/readme.md` — follows Microsoft's
  official Independent Publisher readme template exactly

### Remaining steps (founder action — needs your own Power Platform account)

1. Fork `microsoft/PowerPlatformConnectors` on GitHub.
2. Create a new folder under `independent-publisher-connectors/WhitePact/`
   in your fork and copy the three files above into it.
3. Import the connector into your own Power Platform environment (Power
   Apps → Data → Custom connectors → Import an OpenAPI file) and test it
   — this needs a live Power Platform account, which Claude cannot
   create or access.
4. Take screenshots of the Test operations tab and of 3 unique
   operations succeeding inside a Flow (per Microsoft's PR requirements).
5. Open the pull request against `microsoft/PowerPlatformConnectors`,
   title it `WhitePact Trust Index (Independent Publisher)`, paste in
   the screenshots, and add the `independent-publisher-connector` label.
6. This is a real, external, public PR submission — same category as
   the `xai-org/plugin-marketplace` PR already submitted. Get explicit
   confirmation before actually opening it, even after building
   everything else.

## Mode 2 (Microsoft-certified connector) — blocked

## 1. Partner Center account

- Create/sign in to a Microsoft Partner Center account under WhitePact's
  real business identity.
- This is separate from any personal Microsoft account.

## 2. Publisher / business verification

- Microsoft verifies the publishing entity (business registration,
  domain ownership, or MPN ID depending on account type).
- **Radtech LLP** (WhitePact's planned future legal entity) is not yet
  incorporated as of 2026-08-13 — this step cannot complete until there
  is a real, verifiable legal entity to attach the Partner Center account
  to, or until the founder verifies as an individual publisher if
  Microsoft's program allows it.

## 3. Microsoft 365 / Copilot enrollment

- A Microsoft 365 tenant with Copilot Studio access is needed to build
  and test the certified connector package end-to-end before submission.

## 4. Ownership/control of the MCP endpoint

- Microsoft's certification process typically requires proving control
  of the domain/endpoint being registered
  (`whitepact-mcp-http.onrender.com`, a Render subdomain WhitePact
  controls) — confirm the exact verification method from current
  Microsoft docs at submission time, since these processes change.

## 5. Legal/support information

- `distribution/microsoft/mcp-metadata.json` currently points `privacy`
  and `terms` at raw GitHub content URLs (verified live) rather than a
  branded domain — decide whether that's acceptable for submission or
  whether a real `whitepact.<tld>` domain should exist first.
- Support contact currently resolves to a personal Gmail address
  (`annaduraiguruprasath7@gmail.com`) — decide whether a dedicated
  support address/domain is wanted before this goes in front of a
  reviewer.

## 6. Submission

- Complete Microsoft's actual submission form (contents will differ from
  this package's field names — re-map at submission time).
- Upload icon assets (reuse the existing approved WhitePact logo, resized
  per Microsoft's required dimensions — do not redesign it).

## 7. Review responses

- Microsoft's review process may come back with required changes —
  respond to those directly; this document doesn't anticipate specific
  review feedback since none has been received (nothing has been
  submitted).

## What Claude prepared, ready to hand to whichever human does this

- `distribution/microsoft/intro.md` — product description for the
  submission form.
- `distribution/microsoft/mcp-metadata.json` — canonical endpoint, auth,
  and tool-count metadata (defers to the live server-card for the
  authoritative tool list, so it can't drift).
- `docs/integrations/microsoft-copilot.md` — the technical setup doc
  (Mode 1, works today without any of the above).
