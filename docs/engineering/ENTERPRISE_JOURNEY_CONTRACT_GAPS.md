# Enterprise journey: contract gaps and fixture boundary

Read-only audit against base `01cc0d9b815d7ce27f41cc42fb4853b845003d75`;
Antigravity reference `b3a88396ab4ffcca6b39a78fe2ebe36ac7e60934` inspected read-only.
No backend, frontend, SDK, shared security or existing test changes in this audit.
Antigravity retains P0 security ownership; recommendations are not implementation.

## Evidence discipline

No new browser, Core, PostgreSQL or production journey was executed for this report.
VERIFIED below means only the explicitly named existing executed checkpoint evidence,
not code inspection and not independent qualification. PR #198 checkpoint execution
reported the actual localhost/PostgreSQL customer suite and SDK tests passing at
`f338556baf9984ab485f2d4758179fb87e8baa4d`; that is inherited evidence, not a fresh
run on this audit head. Current source inspection is marked PARTIAL/UNVERIFIED.
The 22 new CrewAI/LlamaIndex consumer tests prove controlled response contracts only.

Antigravity's b3a88396 changes three adversarial test files. Its dashboard `app.py`
has the same SHA-256 as the inspected base:
`1d1aae6f34a175066fc02f3f172720e61ab3dc238b4456b00bb56aa7551a393c`.
`test_p0_approval_resume_adversarial.py` imports `live_customer` from the existing
customer fixture. This does not add initial production authority provisioning.
No assertion that those Antigravity tests passed is made here.

## Exact requested 20-step journey

| # | Step | Status | Actual contract / evidence and limit |
|---|---|---|---|
| 1 | Visit WhitePact | UNVERIFIED | `web/src/App.tsx` public routes and `app.root` static home exist. No fresh browser/deployed availability proof in this audit. |
| 2 | Create organization | PARTIAL | `POST /api/web/onboarding`, `web_onboarding`, attaches organization to authenticated user; existing `_prepare_org` executes it. No complete external evaluator journey. |
| 3 | Verify identity | PARTIAL | Email `POST /api/web/auth/verify` is not identity assurance. Existing `_prepare_org` calls `_apply_idv` using signed development-provider fixture; `/api/enterprise/identity/verification/start` exists, real-provider operational proof absent. |
| 4 | Complete onboarding | PARTIAL | Web onboarding records organization, returns navigation only. It does not establish execution authority. Parent owns onboarding truth correction. |
| 5 | Establish initial organizational authority | BLOCKED | No supported root/consent provisioning HTTP route found. Existing `seed_runtime_authority` directly writes repositories. Core legitimacy design/contract required from Antigravity. |
| 6 | Invite administrators/developers | VERIFIED | Existing real customer checkpoint `_invite_and_accept_admin` executes distinct-human web invitation acceptance. This verifies that tested path, not email delivery/provider availability or all developer role cases. |
| 7 | Assign roles | PARTIAL | `PATCH /api/web/members/{user_id}` plus Members panel exist. Complete hierarchy, last-owner, concurrent membership-change adversarial proof not freshly executed here. |
| 8 | Create/manage apps/agents | UNSUPPORTED | No `/dashboard/agents` or applications management route. Enterprise service-account CRUD exists but is not equivalent to a canonical application/agent inventory or authority grant. |
| 9 | Create secure credentials | PARTIAL | `/api/web/api-keys` creation, rotate, revoke use canonical hosted issuance; `_canonical_hosted_api_key` calls EnterpriseIAM. Existing fixture uses verified development IDV. Real-provider assurance remains external. |
| 10 | Configure policies | PARTIAL | Browser `PolicyPage` invokes `/api/web/policy`, rules and reorder. Customer counter fixture directly inserts PolicyRepository rule; it does not prove UI policy configuration. Lifecycle proposal/approve endpoints exist but current page does not consume them. |
| 11 | Configure delegation/consent | BLOCKED | Bearer `POST /api/governance/delegations`, chain/revoke/descendants/graph exist. No browser delegation/consent management page and no root/consent provisioning endpoint found. Existing DEVELOPER key correctly cannot perform ADMIN revoke. |
| 12 | Integrate SDK/MCP | PARTIAL | Real Python/TS/Go SDK and MCP protocol qualification exists separately; fresh evaluator installation plus no-fixture initial authority is not a complete journey. |
| 13 | Submit real governed tool | PARTIAL | `POST /api/governance/tools/call` via v1 alias exists. Existing real TCP counter journey exercises it after test authority seed. Synthetic local counter is not real customer integration or isolated external effect proof. |
| 14 | Inspect authorization result | PARTIAL | SDK preserves canonical outcomes/UNKNOWN. Dashboard evidence and recent decisions exist; decision/risk explanations are limited to returned fields. Parent owns UI uncertainty corrections. |
| 15 | Complete human approval | VERIFIED | Existing `test_real_distinct_humans_approve_resume_once_and_deny` executed real persisted two-human approval, first-vote pending, duplicate/conflict/CSRF behavior. Test authority is fixture-seeded. |
| 16 | Resume exactly approved action | PARTIAL | Same existing test verifies one local counter dispatch and replay denial. Antigravity b3a adversarial mutation/resume tests are source context only, not independently executed here. No generic arbitrary external-effect guarantee. |
| 17 | Evidence/audit review | PARTIAL | Browser evidence list/detail/verify/attestation and bearer list/attestation exist; tested tenant evidence paths inherited. These are bounded records, not proof of comprehensive privileged-admin auditing or external truth. |
| 18 | Revoke agent/user/key/delegation | PARTIAL | Key revoke and post-revoke denial executed in existing customer checkpoint. Member deletion/service-account revoke/delegation revoke exist. Full in-flight user/agent cascades/outage deadlines belong to Antigravity P0 work. |
| 19 | Safe denial/recovery | PARTIAL | Existing local DB outage test shows new admission fails and recovers to approval. In-flight revocation outage, Linux containment and effect uncertainty are not closed by that proof. |
| 20 | Org settings/lifecycle | PARTIAL | `PATCH /api/web/organization` name update, membership and enterprise lifecycle endpoints exist. Console omits ownership transfer/deactivation/account deletion; not safe to bolt these onto UI without contract/authority review. |

## Hidden authority and policy fixture dependency

Exact symbols:

- `tests/test_v1_exactly_one_effect.py::_prepare_org`: register/verify/onboard,
  development IDV, DEVELOPER key issuance, invite second administrator, then
  invokes `seed_runtime_authority` and `PolicyRepository.add_rule` directly.
- `tests/conftest.py::seed_runtime_authority`: creates synthetic human owner
  `test-owner:{organization_id}`, root evidence `test-root-evidence`, consent
  evidence `test-consent-evidence`, test issuer/source, explicit action/target/
  purpose, one-hour expiry; writes `RootAuthorityRepository`,
  `ConsentProofRepository`, `DelegationRepository` without customer HTTP flow.
- `src/responsibleai/dashboard/app.py::web_onboarding`: organization attachment
  only. `web_create_api_key` / `_canonical_hosted_api_key`: credential issuance,
  not root authority or consent. Scope/IDV/RBAC alone must not imply authority.
- `governance_grant_delegation`: ADMIN-scoped bearer endpoint forwards to canonical
  repository with attenuation checks; it is not a consent/root legitimacy endpoint.

Do not replace this gap with React authority calculation, auto-consent on signup,
owner-role-as-root, broad default grants, direct SQL or a development bootstrap flag.

## Minimal proposed Antigravity API/UI and test contract

Names below are **proposals, not existing APIs**; exact route and canonical schema
must be reviewed by the Core owner. No root-legitimacy algorithm is prescribed.

1. Authenticated, tenant-derived read-only authority-readiness endpoint: canonical
   root legitimacy, explicit consent/delegation validity, purpose/scope binding,
   expiry/revocation status and actionable unmet requirements. Separate configured,
   pending verification, valid and revoked states; never expose secret proof material.
2. If the Core supports a legitimate issuance flow, expose its reviewed application/
   request endpoint with exact approved action/target/purpose/time bounds and explicit
   human consent action. The browser submits intent, not authority IDs/tenant decisions.
   Backend derives organization/principal, validates actual evidence/assurance and
   issues only canonical records under existing privileged control requirements.
3. UI shows why no governed action can proceed, links to verified supported provisioning
   path, and displays returned status without inferring ALLOW. Existing key remains
   a credential. No UI can turn billing/service availability into authority.
4. Positive test: fresh database + actual web signup/login/org/provider verification
   + reviewed provisioning HTTP + actual policy HTTP + first governed tool request;
   **no root/consent/delegation repository fixture writes**. Assert exact tenant,
   canonical binding, approval/evidence and one effect at actual guarded boundary.
5. Adversarial tests: absent/expired/revoked root/consent, forged org/principal/proof,
   unverified legitimacy, broader delegation, target/action/purpose substitution,
   stale epoch, concurrent approvals/replay, malicious second tenant and DB outage.
   Assert zero effects and no synthesized grants. Lost response remains uncertain,
   not automatically replayed. Antigravity owns source implementation/qualification.

## Dashboard capability map (not invented UI contracts)

| Missing/limited console area | Existing backend capability | Integration constraint |
|---|---|---|
| Apps/agent inventory | `enterprise/router.py` service-account GET/POST/DELETE; governance intent-contracts and passports | Service accounts are not authority or a full app model; require explicit supported domain mapping. |
| Delegation and consent | `app.py` delegation grant/chain/revoke/descendants/graph | Bearer ADMIN paths cannot simply be invoked as browser-session CSRF contracts; consent/root missing. |
| Incident/containment view | `app.py::report_incident`, `/api/incidents` list/detail | Reporting incident is not containment status. No browser incident console or validated session adapter observed. |
| Policy review lifecycle | `/api/web/policy/changes/propose` and `/{approval_id}/approve` | `PolicyPage` invokes rules/reorder directly; reviewer workflow needs returned contracts and current backend decision. |
| Organization lifecycle | `enterprise/router.py` deactivate/ownership transfer, web account deletion | Destructive privileged flows require explicit UX/step-up/confirmation contracts; not an automatic V1 addition. |
| Security enrollment | `enterprise/security/router.py` passkey/TOTP/recovery/session routes | Existing Security panel says management unavailable in V1; verify browser-auth compatibility before controls. |
| SDK/MCP setup | `/docs`, API keys and supported SDK endpoints | Must explain explicit authority prerequisite, not key creation as readiness. |

## Concrete frontend truth / link defects found by source inspection

1. **Bounded counters labeled as overall metrics**: `OverviewPage.tsx` summary rail
   labels “Governance decisions”, “Agents”, “Blocked actions”.
   `app.py::web_dashboard_summary` loads **at most 50 evidence records** and computes
   unique agents only in those records; pending approvals also max 50. This is neither
   total usage nor managed agent inventory. Small safe frontend correction: label
   the recent bounded window/counts and do not imply lifetime totals. No fake usage.
2. **Initial action guidance skips authority prerequisite**: same page's empty-state
   “Connect your first agent and WhitePact will begin evaluating configured actions”
   with “Create an API key” CTA does not mention missing canonical authority/consent.
   Correct factual wording now; do not fabricate readiness data before contract exists.
3. **README anchor suspicion INVALIDATED**: `DocsPage` links to the frozen
   `c1d7803fce0787f9183e18bb38134f73a6c0f57d` README, not this worktree's current
   README. Coordinator checked that exact Git object: its heading is
   `30-second quickstart`, matching the existing fragment. No link change is needed.
   The initial audit compared the wrong version; no live-link crawl is claimed.
4. **Policy outcome selection omits redaction**: `PolicyPage.tsx::EFFECTS` is
   ALLOW/DENY/REQUIRE_APPROVAL/QUARANTINE. This alone is not proof the rules endpoint
   supports ALLOW_WITH_REDACTION; inspect canonical PolicyRuleRequest before adding it.
   Preserve unknown/redacted returned outcomes, avoid inventing editing support.

These findings were sent to the coordinator; only this document is changed here.
No fresh accessibility, responsive, browser, deployed-domain or broken-link PASS is
claimed. No public universal control/certification defect was confirmed in the scoped
corporate copy inspected; that is not a comprehensive public claims audit.

## Remaining authority and release state

Initial production root/consent provisioning remains a **BLOCKED Core contract**.
In-flight revocation, Linux containment, billing concurrency, evidence witness and
CodeQL P0s remain Antigravity-owned. Provider verification and production operations
remain externally unqualified. This audit does not change gate status.
No source modification, push, merge, deployment, DNS/cloud mutation or publication.
Production remains **NO-GO**.
