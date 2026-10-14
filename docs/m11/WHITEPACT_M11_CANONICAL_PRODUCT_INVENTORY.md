# WHITEPACT M11 CANONICAL PRODUCT INVENTORY
Inspected source parent: 62be9caa70e6c2eb1c4782a64554323646d987e0.
M10 reference: c801f33f369e3727360bc55d6df15083025dc754, read-only and not merged.
This is a source-backed truth register, not production certification.

## Product identity

Formula Ω is the existing `responsibleai.formula` domain library. Gate 2
authority/graph/trace primitives and Gate 3 capability closure are implemented.
The package header still names Gate 2; historical Gate 1 documents describe a
development stage, not current hosted capability. Formula does not itself enforce
runtime execution. No SafeFutureEnvelope, OmegaJudgmentEngine, FormulaProofEngine
customer HTTP service, production subscription tier or Omega-specific dashboard
was found. Do not rename Sovereign results as Formula Omega judgments.

WhitePact Cloud names hosted operational/product surfaces, not a separate
`cloud` authorization engine. The source includes web sessions, organizations,
credentials, policy, approvals, evidence and Paddle integration. No authorized
production deployment/availability or fixture-free root/consent onboarding is
established by their presence.

## Source and access matrix

VERIFIED below is scoped to executed tests, never universal enforcement.
All API references are existing source interfaces; legacy/bearer routes are not
assumed safe browser routes. Database revision head is 0063, but schema presence
is not a deployed migration proof.

| Subsystem / purpose | Actual implementation and API/UI | Data / required services | Evidence / status / owner / missing acceptance |
|---|---|---|---|
| Formula Ω authority domain | formula/authority algebra, containment, context matching, root/delegation models | Pure Python, no customer DB/API or services | tests/formula 146 domain/property/adversarial tests executed; VERIFIED domain library only; Antigravity semantics; hosted Omega judgment NOT FOUND |
| Formula graph / trace / epistemic | formula/graph snapshots, trace semantics, epistemic lattice, CommitFence | In-memory domain inputs; no production runtime boundary | Gate 2 suites; VERIFIED tested semantics only; not external grants or audit execution |
| Formula capability closure | formula/capability/closure.py compute_capability_closure, witness DAG/budgets/provenance | Pure domain graph/state inputs | Gate 3 suites; VERIFIED tests, customer UI/API UNSUPPORTED; owner security domain |
| Core governance | governance/gateway.py WhitePactRuntimeGateway; execution authorization/admission; /api/governance/tools/call | Canonical PostgreSQL policy/authority/nonce/epoch/approval/evidence; isolation backend | Real local SDK/TCP tests PARTIAL with authority fixtures; Antigravity; legitimate customer provisioning and independent runtime qualification missing |
| Constitution/root/consent/Heart | governance/root_authority, consent_proof, authority_resolver, heart_veto; named repositories | Durable root, consent and revocation state, verified responsible principal | No supported browser initial issuance flow found; BLOCKED; Antigravity canonical contract required |
| Delegation/capability boundaries | governance/delegation_kernel, delegation_graph, authority_lattice; bearer delegation create/chain/graph/revoke | Durable delegations/epochs with exact scopes | Source/API present, PARTIAL; no browser adapter assumed; M10 changes delegation_repository and adversarial tests, not signup root issuance |
| Policy/risk/judgment | governance/policy.py ordered rules; risk assessment; web policy rules/reorder/history and tiered changes | Durable policy versions/history; step-up/four-eyes services | Three ordered effects versus five runtime outcomes distinguished; existing unsupported effects safe HTTP422; UI/history tests VERIFIED scoped; activation/rollback/step-up ceremony PARTIAL |
| Human approvals | persisted approvals/votes, exact execute; /api/web/approvals/{id}/resolve and /execute | Distinct principals, current authority, durable execution/evidence | Real local quorum/replay/revocation tests; PARTIAL core qualification; UI lost vote/effect handling VERIFIED |
| Execution grants/admission | governance/execution.py and runtime authority_kernel; short-lived ExecutionAuthorization, nonce/version checks | PostgreSQL canonical requests/authorizations/attempts/fences | No client-minted transferable grant endpoint invented; PARTIAL; Antigravity final enforcement |
| Isolation and containment | isolation/container_backend.py DockerContainerBackend, broker/in-flight controls | Native Linux/Docker deployment for claimed containment | Source/test surfaces exist, active M10/security qualification separate; BLOCKED production; no browser flag can enable protection |
| Controlled egress | net and isolation/container broker | Independently enforced target/DNS/transport boundary | PARTIAL source/tests; Antigravity; no Cloudflare/cache fallback authority |
| Evidence/outcome/reconciliation | governance/evidence, evidence_publication, evidence_witness, evidence_bundle; tenant web list/detail/verify/attestation | Durable outcome/evidence chain, witness/signing stores where configured | Web attestation contract is unsigned; bounded export does not mint a signature; PARTIAL full integrity; signing/witness owner Antigravity |
| IAM/account/session | enterprise/EnterpriseIAM, dashboard get_web_principal/require_web_csrf, OAuth/OIDC/SAML | User/session/org/membership/environment schemas, external identity providers | Account/session UI supported; session 503 != expired and malformed acknowledgements fixed; PARTIAL true provider assurance; identity != authority |
| Applications/agents | No canonical app/agent registration contract found; no customer inventory | New schema requires compatibility/ownership review | UNSUPPORTED; proposed non-authorizing metadata lifecycle is not silently implemented as service accounts |
| Service accounts / credentials | enterprise service-account API, keys/environment/eligibility endpoints | Durable credential principals and scopes | IMPLEMENTED UNVERIFIED in customer console; not equivalent to agent topology or authority; security owner review required for lifecycle associations |
| Members/org lifecycle | web invitations/member role/removal and organization settings; enterprise lifecycle routes | Durable memberships, sessions/tombstones, role constraints | Supported subset PARTIAL; invitations do not establish root; destructive ownership transfer/erase not bolted into UI |
| Paddle commercial billing | billing PaddleBillingService, signature checks; web checkout/portal, /api/billing/paddle/webhook; Stripe legacy | Mirrored customer/subscription/event state, approved provider environment | Paddle-first UI exists; live commercial validation not run; PARTIAL; Antigravity security-sensitive concurrency; entitlement != execution authority |
| Sovereign inspection/simulation | SovereignService, tenant-derived /api/web/sovereign/*; capabilities, X-Ray, effective/compare/drift, explain/trace, simulations, policy lab, recorder, time machine, capsules | Existing canonical Core/evidence inputs; shadow persistence; session/CSRF | Separate product; production fixtures forbidden, manifest expectations declared only; PARTIAL live contract integration, Authority BOM EXPERIMENTAL; not Formula Omega runtime judgment |
| MCP | server/governance_integration/trust_domain/upstream; stdio/Streamable HTTP/legacy SSE; whitepact-mcp aliases | Auth/canonical Core for enforced hosted paths; stdio advisory | 42 protocol tests inherited exact source; VERIFIED tested protocols, production-client compatibility UNVERIFIED |
| Python/TypeScript/Go SDKs | rai_client / @responsibleai/client / legacy Go module; GovernanceRuntimeClient APIs | Supported server endpoints, caller credentials | #202 SDK/package tests green; five outcomes and one-shot uncertainty preserved; source installation supported, unpublished SDK registry names cannot be assumed available |
| Trust Index/passports | trust score/badge/passport/registry and trust-index routes | Local assessments/registries and relevant identity records | PARTIAL project scoring; not independent SOC/ISO certification or proof of all execution paths |
| Guardrails/BiasBuster/PrivacyLabel | guardrails/content scanning, biasbuster/privacylabel namespaces, /api/evaluate and scan | Analytical inputs/models and optional data dependencies | PARTIAL analytics; prompt/content classifications are not execution authority |
| Hallucination/evaluation | hallucination detector, benchmark/dataset/comparison/regression helpers | Analytical datasets/provider configuration | IMPLEMENTED UNVERIFIED for broad customer acceptance; heuristics not truth guarantees |
| Cost/drift/redteam/compliance/supply-chain | Existing analytical/backend/MCP modules, legacy templates | Tool-specific datasets/storage and optional providers | PARTIAL; legacy templates/source presence not modern console capability or security clearance |
| Incident/containment operations | incidents logic, incident/public incident repositories and legacy surfaces | Durable tenant incidents and canonical containment state | PARTIAL; no fabricated timelines, incident acknowledgement/revocation contract must be reviewed before exposing mutation |
| Data governance | inventory/classification/retention/legal holds/export/erasure/tenant deletion/tombstones/restore readiness | Durable retention/deletion state, backup crypto/restore environment | PARTIAL; irreversible customer lifecycle/retention guarantees unqualified and security-owned |
| Operations/observability | /api/health, /api/metrics; dashboard logging/prometheus, ops preflight/admission/backups, audit/SIEM delivery | PostgreSQL/Redis/isolation/dependency services; sanitized telemetry | PARTIAL service operation; health != authorization validity; no private inputs exposed by new instrumentation |
| Corporate website/dashboard | React App routing, public docs/trust, auth/onboarding, current console and Sovereign | Built frontend assets plus authenticated backend | Current M11 changes compiled/fixture-browser tested; full actual cloud journey BLOCKED; Codex |
| Cloud infrastructure | Terraform modules, deploy ingress/operational artifacts and nine-platform model | Approved Linux/API/database/executor topology, IAM/secrets/regions/backup/monitoring | Two locked modules validated using native tool; nine-provider deployment PARTIAL/BLOCKED; no provisioning or spend |

## Versions and publication — actual official registry observations, 14 October 2026

- Source platform and SDK versions: 1.3.1. This is not a published M11 release.
- [Official PyPI platform metadata](https://pypi.org/pypi/rai-governance-platform/json):
  latest returned 1.2.6; source 1.3.1 absent from releases.
- [Official PyPI Python SDK metadata](https://pypi.org/pypi/rai-client/json):
  HTTP404. Do not tell evaluators to install an assumed published rai-client package.
- [Official npm SDK metadata](https://registry.npmjs.org/@responsibleai%2fclient/latest):
  HTTP404. Use reviewed source builds/tarballs, not an invented npm release.
- MCP registry manifest intentionally has record version 1.2.3 and package 1.2.2.
  [The declared PyPI 1.2.2 artifact exists](https://pypi.org/pypi/rai-governance-platform/1.2.2/json).
  M11 pins uvx --from to that exact declared version; it does not change published
  registry records or pretend 1.3.1 is available.
- Go module keeps its legacy ResponsibleAi path for compatibility; external
  qualification with a local replace is not proof of a newly published remote module.
- Historical freeze/qualification reports and the website's approved older source
  reference are historical evidence, not M11 independent approval.

## Mandatory acceptance dependencies

Customer Gates 3/4 remain BLOCKED until legitimate root/consent and a canonical,
reviewed application/agent contract are supplied. Roles, billing, credentials,
Sovereign simulations and Formula library objects cannot fill that gap.
No M10 automatic merge, public signup/deployment, cloud/DNS change, release tag
or package publication follows from this inventory.

