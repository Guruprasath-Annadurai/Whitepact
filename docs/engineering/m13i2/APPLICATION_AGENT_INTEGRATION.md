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

## Ordinary organization-name update followup

The organization domain now uses a dedicated **read-only by default** `OrganizationSettingsPage`; membership, billing, approval, evidence and security sections retain their existing implementations. The earlier inline form accepted any successful HTTP response and substituted its local draft name. That optimistic substitution and the production rename form are removed. The customer sees the actual server-returned name and a plain message that name changes are unavailable pending workspace confirmation.

Verified source contract: `dashboard/app.py:web_update_organization` is exposed through the existing web/v1 aliases, requires the normal web CSRF dependency, obtains the authenticated admin organization through `_web_org_admin`, updates that organization's name and returns exactly `{id: org_id, name: req.name.strip()}`; request length is 2–200 characters and a missing organization returns 404. The consumer sends only a trimmed `name` in PATCH `/api/v1/web/organization`; it sends no tenant/role/ownership payload. This is ordinary account metadata, not authority provisioning.

The separate GET `/api/v1/web/dashboard/organization` must return one matching authenticated-organization record with `source: organization_repository` and `domain: organization`. Only supported ID/name/slug/plan fields are projected. Incorrect tenant, malformed response and unavailable reads cannot populate the view. The signed-in person is labeled **Signed-in user**, not incorrectly inferred to be the organization's owner.

The mutation/reconciliation preparation is retained only behind an explicit internal `renameContractVerified` prop whose default is false. **The route supplies no true value.** Neither session role nor a runtime feature flag enables it. Tests exercise this preparation seam directly to keep the future implementation reviewable; they are not evidence that the missing backend precondition exists. In that preparation only, OWNER/ADMIN is an affordance and the backend independently authorizes PATCH.

The preparation's synchronous in-flight guard prevents repeated submissions. A valid PATCH acknowledgement must match both the authenticated organization ID and exact submitted name; even then, a fresh GET must confirm the name before any success statement. A concurrent different server name is displayed without a rename-success claim. Lost, malformed or 5xx acknowledgements hide the edit form and keep another rename disabled until an explicit current-state GET succeeds. Failed reconciliation remains locked. There is no automatic PATCH retry. A later successful reconciliation reports current state while preserving that the earlier operation's outcome was unconfirmed; it does not claim causality.

In the preparation, access/not-found refusals hide the form and require a fresh read; ordinary validation/rate-limit rejections do not become uncertain success. GETs are cancellable. Component identity includes authenticated organization and user, so old reads or late PATCH acknowledgements cannot populate a switched tenant; unsafe mutations are not aborted as if cancellation proved rollback. This does not prove that the mutation targeted a previously rendered tenant or that an interrupted mutation was rolled back.

The new organization tests cover semantic acknowledgements, independent persisted-state read, duplicate submission, malformed/foreign/mismatched success, lost acknowledgements, failed reconciliation, concurrent server changes, refused updates, wrong-tenant reads, stale GET/PATCH responses and viewer affordances. Root integration owns the actual ordinary HTTP rename/reload acceptance; this worker's tests exercise frontend behavior with explicit response fixtures.

**Rename activation BLOCKED:** the existing PATCH is pathless and selects its target from the current session cookie. It accepts no expected-organization/version precondition. The browser can detect a mismatched acknowledgement and suppress stale presentation, but that cannot undo a rename if another tab switched the shared session cookie before the server processed PATCH. A preflight read cannot eliminate that race. Backend owner must supply and independently qualify an atomic expected-organization/version contract before production UI activation. The existing normal-session HTTP rename proof is separate and does not qualify this cross-tab race. No client-invented request field/header is presented as enforcement.

Followup validation after default-disabled gating: **31 frontend test files / 289 tests passed**, including **14 organization-specific tests** and the actual-route no-form/no-PATCH test. Focused organization/dashboard rerun: **38 passed**. Complete ESLint, TypeScript (through production build), production build with retained static bundle, and `git diff --check` passed. `FRONTEND_ACCESSIBILITY.md` is intentionally left to the parent integration owner so its independent browser acceptance record is preserved.
