# Microsoft Copilot certification — founder submission checklist

Nothing in this checklist has been done. This lists exactly what a
Microsoft-certified (Mode 2) connector submission requires, so the
founder can decide whether it's worth pursuing, and do it without
re-deriving these requirements from scratch.

**Claude did not, and will not, do any of the following** — each needs an
account, a legal identity, a payment, or a UI confirmation only the
founder can provide.

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
