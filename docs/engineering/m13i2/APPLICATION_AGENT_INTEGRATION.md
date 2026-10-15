# M13-I2 application and agent integration

GLOBAL PRODUCTION NO-GO. This change adds ordinary read-only customer presentation; it does not qualify or enable privileged workflows.

Reviewed starting commit: `8cb692b99fb4b1fa894e07d432105209f430b0f7`, isolated branch `codex/whitepact-m13-i2-customer-console`.

## Actual customer read contracts

| Product surface | Existing backend contract | Integration and limits |
| --- | --- | --- |
| Agent registrations | `GET /api/enterprise/organizations/{org_id}/authority/agents` | Existing Agents page retained. Reader validates session-addressed tenant context, record shapes and unique IDs. Lifecycle labels and delegation flags remain reported data, never action authorization. |
| Root and consent record status | `GET /api/enterprise/organizations/{org_id}/authority/status` | New on-demand panel inside Agents. Shows validated record-pair flag, projected root/consent IDs and reported epoch only. No scope reconstruction, execution permission or live revocation guarantee. |
| Application inventory and ownership | No integrated customer list/ownership contract identified | BLOCKED. No endpoints, applications, owner assignments or organization-to-application ownership inference invented. |
| Effective executable capabilities | Agent list does not enumerate effective capabilities; status lists underlying records, not full effective permission evaluation | BLOCKED. Neither registration, delegation flags nor root/consent presence is promoted to executable authority. |
| Privileged lifecycle actions | Actual customer prerequisite chain remains separately qualified by security owner | BLOCKED. No enrollment, bootstrap, consent, delegation, containment, recovery or revocation controls added. |

`enterprise/authority/router.py` routes both reads through `_web_actor`; the service's `_verify_tenant_and_role` requires matching organization and OWNER/ADMIN. `get_authority_status` derives `has_active_authority` from unrevoked root and consent rows. That derivation is not a full expiry, effective capability, recovery or execution decision. The interface deliberately calls this a backend-reported record pair.

M13-I1's actual fresh-PostgreSQL customer attempt recorded successful owner-session status and registration GETs in `docs/engineering/m13i1/CUSTOMER_JOURNEY_MATRIX.md`. This change consumes those existing reads; it does not claim a new live authenticated journey or independent backend security acceptance. Parent integration owns fresh exact-head backend/customer validation.

## Read lifecycle and tenant handling

The status panel submits no request until the customer selects **Read reported root and consent status**. It uses only the authenticated outlet organization's ID for addressing. The shared API wrapper provides same-origin credentials and its existing bounded read timeout. The panel never sends mutation bodies, retries automatically or stores credentials in UI state.

Every refresh invalidates its previous snapshot immediately. Failures, 401/403 responses, invalid tenant payloads and timeout cannot become inactive/empty/successful states. Manual retry is available. Root/consent IDs and epoch are shown only after strict response validation; unrelated server fields are not rendered. IDs wrap for narrow viewports.

The Agents page keys the status panel by organization. A tenant change aborts pending work, removes prior records, resets the panel to unrequested and ignores late acknowledgements. Inventory retains its own independent abort/stale-response protection. Status failure does not turn a successful inventory read into failure, and inventory failure does not imply an authority state.

Inventory now also has an explicit refresh control after successful reads. A failed refresh hides the prior list, presents one error announcement and permits manual read retry. The inventory region exposes busy state during pending reads. Existing local filtering/pagination remain confined to returned registrations; no server pagination or complete-inventory claim is added.

## Required backend owner handoffs

- **Application backend/product contract owner:** supply an authenticated tenant-scoped application identity/list contract, ownership semantics distinct from organization membership, response schema and stable pagination/filtering behavior. Product cannot implement ownership from the current agent principal list.
- **Security authority owner:** define whether a customer-facing effective-capability read is supported, with authoritative evaluation time/scope, policy/delegation/revocation semantics and safe handling of unavailable/partial evaluation. Existing status/delegation records are insufficient to reconstruct it in the browser.
- **Security/customer acceptance owner:** independently qualify privileged prerequisites and real user journeys. Ordinary record reads do not remove existing origin, passkey, consent or execution gates.

No backend, security-owned source, database schema, existing security regression, deployment or cloud resource was changed.
