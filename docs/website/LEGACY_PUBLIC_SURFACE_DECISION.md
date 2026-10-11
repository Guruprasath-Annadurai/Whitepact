# Legacy public surface decision inventory

Repository baseline: `52d9b3c5497af24bb7d4a7147e33deaadc64296e`.
This document proposes owner decisions. It does not retire a route, delete a
resource, modify a proxy, change authentication or deploy a redirect.

## Existing public resources

| Route / source | Proposed disposition pending owner review | Reason / decision evidence needed |
|---|---|---|
| `/registry`, `/leaderboard`, `/assess`, `/verify/{passport_id}`; `dashboard/app.py` and matching `dashboard/static/*.html` | RETAIN | Existing public trust data and citation/badge links may depend on them. Confirm current ownership, methodology and data validity before promoting them; later branding review requires owner approval. |
| `/incident-db`, `/incident-db/report`, `/incident-db/{public_id}` and matching static pages | RETAIN | Publication, moderation and historical references need a separate owner decision; avoid silent data/link loss. |
| `/status`, `dashboard/static/status.html` | RETAIN | Existing source calls it a self-hosted stopgap; it does not prove global service uptime. |
| `/trust/legacy`, `dashboard/static/trust.html` | REBRAND (proposal only) | Preserve useful disclosures after claim/evidence review and owner approval. A future redirect would require a separate parity and continuity decision. |
| `/llms.txt`; `web/public/llms.txt`, generated package copy and `dashboard/app.py` handler | REBRAND (implemented locally) | Phase-1 now serves WhitePact corporate links and qualified boundaries from the generated file; the earlier ResponsibleAI text is historical. This does not retire registry or incident resources, and live deployment identity remains unknown. |
| `/refunds` | REDIRECT (existing source behavior) | Existing 308 redirect to `/refund-policy`. Live deployment identity and observed behavior remain separate evidence. |
| Legacy governance shell routes and static assets | RETIRE LATER (future owner decision) | Preserve existing retirement controls and community compatibility. These are product surfaces, not resources to relabel as corporate pages; no new retirement configuration change is authorized here. |

RETAIN preserves the resource; REBRAND changes its presentation only; REDIRECT
requires explicit destination/status/continuity evidence; RETIRE LATER leaves a
future retirement decision open. Proposed dispositions are not authorization.

## Existing governance retirement boundary

`src/responsibleai/dashboard/legacy_frontend.py` lists legacy governance routes:
`/auth/complete`, `/evaluate`, `/guardrails`, `/hallucination`, `/cost`, `/router`,
`/trust-scores`, `/eval`, `/redteam`, `/audit`, `/incidents`, `/webhooks-manage`,
`/organizations`, `/billing`, `/settings`. It also inventories old HTML and
`/static/js/app.js`, `/static/js/i18n.js`, `/static/css/app.css`.
Shell files live under `dashboard/legacy_templates/`, outside the regular static
mount. The existing middleware/static allowlist returns the existing retirement
response when `WHITEPACT_UNIFIED_SAAS` is true, settings are production, or the
MCP trust domain is enterprise. Community behavior remains separately defined.

Public registry/leaderboard/assessment/verification/status/trust/incident static
resources are explicitly allowed by the existing unified static allowlist. The
shared ResponsibleAI label does not make all of these resources retired shells.
The HTML shell being reachable is also distinct from permission to access data
or execute actions; existing backend checks remain authoritative.

`helm/rai-governance/templates/configmap.yaml` does not directly emit
`WHITEPACT_UNIFIED_SAAS`; `templates/deployment.yaml` permits `extraEnv`. The
retirement decision also depends on effective production/trust-domain settings.
Example chart values cannot prove the public service's effective configuration.
Ingress routes and external Compose TLS proxy mappings must be inspected by the
operator before attributing a live legacy response to any particular flag.

## Owner decision gate

For each future redirect or retirement, record owner, route, inbound link/API
consumers, retained data, replacement scope, status code, cache consequences,
rollback and acceptance evidence. Review crawler/sitemap references and public
resource disclosures together. Keep API/resource continuity and authenticated
workspace behavior intact unless separately authorized. No resource retirement,
kernel/authentication/security change or deployment is performed in this phase.
