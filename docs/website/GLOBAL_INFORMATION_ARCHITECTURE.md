# Global corporate information architecture — Phase 1

Implementation base: `52d9b3c5497af24bb7d4a7147e33deaadc64296e`.
This document records the architecture used by the local Phase-1 implementation
and its Phase-1B corrections. It is not deployment evidence. No deployment is authorized.

## Navigation and audiences

One corporate navigation: Product `/product`, Architecture `/architecture`,
Developers `/developers`, Security `/security`, Enterprise `/enterprise`,
Docs `/docs`, Company `/about`. Secondary GitHub link. Primary CTA: Get started
at `/docs`; hosted signup is not the dominant CTA while deployed readiness is
unverified. `/` remains the corporate entry. Sovereign has a public product
page linked from Product and the footer; its Workbench remains a product surface.

## Page responsibilities

- Home: category, problem, independently enforced supported boundary, next step.
- Product: what evaluation, grants, governed execution and evidence do.
- Architecture: the control chain, authentication versus authority, evaluation
  versus enforcement, TCB/integration limits and failure/UNKNOWN behavior.
- Developers: supported CLI/Python/source TypeScript/MCP/API entry points.
- Docs: task-oriented setup, first action prerequisites, results, approval,
  evidence and troubleshooting; exact current reference links.
  Bearer integrations list evidence through `GET /api/governance/evidence`;
  `GET /api/web/evidence/{evidence_id}` requires a browser session and organization
  membership. Linked baseline SDK detail helpers reference an unavailable route;
  their presence is not proof of a working detail interface.
- Security: control scope, failure/replay/revocation boundaries and disclosure.
- Enterprise: deployment, identity/lifecycle, tenant, evidence/SIEM and operator
  responsibilities; implementation is not commercial availability/certification.
- Trust: Control → Scope → Evidence → Limitation with explicit status.
- Company: factual project responsibility/philosophy/contact; no invented team.
- Contact: evaluation, disclosure, general contact using verified existing paths.
- Pricing: withhold numerical paid proposals and annual terms pending owner
  reconciliation; distinguish evaluation choices from PRO/ENTERPRISE runtime plans.
- Terms/Privacy/Refunds: factual current provider information; counsel gate stays.

## Owner decisions still open

Commercial offer approval, legal seller identity/address/jurisdiction, contact
ownership and support/privacy validity require owner evidence. Counsel review,
provider activation and deployed build identity each remain separate gates.
The website uses the existing published project contact for inquiries, without
asserting a verified legal seller, staffed support organization or approved offer.

## Route policy

Corporate pages are anonymous HTML with route-specific static metadata/content.
Browser product shells can be delivered without a session; their data and actions
remain protected by existing session/API authentication. Do not make the website
change those protections. Account/product shells receive server-delivered noindex.
Unknown public URLs return HTTP 404. Legacy resource changes require separate
approval; this phase inventories them and does not delete or retire them.

## Editorial invariants

The agent may think freely. It may plan freely. But it cannot act outside
independently enforced authority.

The doctrine describes supported, configured enforcement paths, not control over
arbitrary code outside WhitePact's trusted boundary. No unsupported feature,
package, customer, security certification or production-availability claim.
