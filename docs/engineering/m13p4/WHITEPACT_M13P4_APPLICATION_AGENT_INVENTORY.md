# M13-P4 application and agent inventory

Status: **READ-ONLY AGENT REGISTRATION VIEW; APPLICATION/CAPABILITY INTEGRATION BLOCKED**. GLOBAL PRODUCTION NO-GO.

## Contract evidence

- `src/responsibleai/enterprise/authority/router.py`, `GET /agents`, obtains the web actor and delegates to the authority service.
- `src/responsibleai/enterprise/authority/service.py`, `list_agents`, checks tenant/role and returns registered AI-agent principals and a reported delegation flag. Returned fields include agent ID, organization ID, display name, lifecycle state, framework, creation time and delegation ID. It does not return application ownership, executable capabilities, a total count or pagination cursors.
- `src/responsibleai/dashboard/app.py`, `web_dashboard_domain`, accepts legacy `agents` as a domain but falls through to `items: []`, `source: not_available`. This is unavailable integration, not evidence of an empty customer inventory.
- No customer application inventory or application ownership endpoint was identified in the inspected Python API sources. A sovereign model's optional application ID is not an inventory/ownership contract.
- `web/src/lib/customerAuthorityReader.ts` derives path addressing from session organization context, rejects malformed identifiers, rejects cross-organization/duplicate/malformed agent records and projects only supported display fields. The agent read supports ordinary customer read integration; its separate authority-status read remains preparation only. These consumer checks do not independently qualify privileged backend security.

## Product work delivered

`AgentInventoryPage` connects the existing agent-registration GET to the authenticated dashboard organization. It cancels obsolete requests and ignores late results after tenant or retry-attempt changes; no previous-tenant records are shown during a transition. Failure requires explicit manual retry. Session expiry, refused access and unavailable reads do not become empty inventories. The shared inventory component defaults to its original preparation presentation; the customer page explicitly selects the read-only customer presentation.

The inventory provides a labeled search input matching loaded IDs, names and literal lifecycle labels. It displays at most ten loaded registrations per local page, provides named previous/next controls and announces matching counts. Filtering resets local pagination; smaller refreshed data clamps the displayed page. This makes no server-pagination or inventory-completeness claim.

Ownership and capabilities are explicitly unavailable. Registration, a lifecycle label and a delegation flag never imply execution authority. Missing capability data is not rendered as an empty capability set or as permission denial. Existing loading, unavailable, failed-read and genuinely empty-return states remain distinct. Disabling the read contract or entering error/loading state hides prior records and browsing controls immediately.

Dashboard owner integrated `/dashboard/agents` and the Agents navigation entry. No backend endpoint, security-owned source or authority mutation was added or enabled. No application records, owners, capabilities or tenant identities are fabricated.

## Acceptance and unresolved contracts

| Requirement | Result |
| --- | --- |
| Application inventory / ownership | BLOCKED: no integrated customer read contract |
| Agent inventory / status | Existing backend-connected ordinary registration read; unknown status labels preserved; no authority inference |
| Capability visibility | BLOCKED: backend list does not supply executable capabilities |
| Empty/loading/error | Covered by existing preparation tests |
| Pagination/filtering | Accessible local browsing of returned records only; server pagination remains unavailable |
| Tenant isolation | Ordinary real-session own/foreign-tenant GET regression and retained reader payload-rejection tests; independent privileged security qualification remains required |
| Privileged lifecycle actions | BLOCKED; no controls added |

Focused validation: `cd web && npm test -- src/test/m12p-inventory.test.tsx src/test/m13p4-inventory.test.tsx --maxWorkers=1` — **2 files, 10 tests passed**. Covers default gating, all read states, unknown status, unsupported capabilities/ownership, local page boundaries, filtering and removal of stale presentation on failure/unavailability. This is component regression evidence, not live backend qualification.

Retained reader regression: `cd web && npm test -- src/test/m12c-authority-reader.test.ts --maxWorkers=1` — **1 file, 28 tests passed**. Focused ESLint for the changed component/test and inventory-scoped `git diff --check` passed.

Backend ordinary read regression: `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/python -m pytest tests/test_m13p4_inventory_read_contract.py -q --no-cov -x` — **1 passed**. Creates real verified customer owners, workspaces and sessions through normal repositories/services; performs no bootstrap, agent registration, delegation or authority seeding. Own-tenant GET returns a confirmed empty list, unauthenticated GET returns 401, and foreign-tenant GET returns 403. SQL capture confirms only standard session `last_seen_at` and request audit bookkeeping writes; no inventory/authority mutations. This does not independently qualify privileged workflows or prove a populated real-server inventory journey.

Integrated focused frontend regression: `cd web && npm test -- src/test/m13p4-inventory-page.test.tsx src/test/m13p4-inventory.test.tsx src/test/m12p-inventory.test.tsx src/test/m12c-authority-reader.test.ts --maxWorkers=1` — **4 files, 42 tests passed**, including real reader request shape, manual retry, abort/late tenant response handling, and cross-tenant response rejection.

Environment correction: the reused Python virtualenv is editable against another checkout, so `PYTHONPATH=src` is required. An initial invocation without that setting failed in the older checkout's `_epoch_now` fixture; this was an environment error. An initial overly strict SQL assertion rejected existing audit/session bookkeeping; the final assertion permits only those exact bookkeeping statement types. Neither failure caused backend/security-source changes.
