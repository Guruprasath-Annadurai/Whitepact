# WhitePact Data Flow and Record of Processing Activities (RoPA) Baseline

**Status:** First-party processing inventory/readiness record; not legal advice  
**Review date:** 2026-09-13  
**Owner:** WhitePact maintainer / privacy contact

## Purpose

Maintain a practical baseline of personal-data processing for Provider-operated WhitePact services. This supports privacy governance, GDPR accountability, India DPDP readiness, vendor reviews, enterprise questionnaires and future counsel/auditor review.

Self-hosted customer deployments are generally customer-operated and outside Provider's direct processing unless support/telemetry or another contracted data flow gives Provider access.

## Processing inventory

| ID | Processing activity | Data / data subjects | Purpose | Working legal-basis assumption* | Systems/recipients | Retention baseline | Security / notes |
|---|---|---|---|---|---|---|---|
| ROPA-01 | Organization/account administration | organization name, account/contact data, authorized-user metadata | provide/administer service | contract / legitimate interest as applicable | WhitePact app, Supabase; relevant support systems if used | account life + policy-defined post-termination period | RBAC, tenant scoping, least privilege |
| ROPA-02 | API authentication and authorization | API-key metadata/hash, role/scope, timestamps | authenticate/authorize requests | contract + security legitimate interest | WhitePact app/database | lifecycle of key/account + security/audit needs | raw API key not stored; revocation supported |
| ROPA-03 | MFA/SSO authentication | MFA secret/backup-code data where enabled; identity-provider claims | secure human access | contract/consent/security basis subject to counsel | WhitePact + customer IdP | enrollment/account lifecycle | field encryption where implemented; customer IdP shared responsibility |
| ROPA-04 | Audit/security logging | endpoint/action metadata, timestamps, status, optional IP and governance/evidence metadata | security, accountability, troubleshooting | legitimate interest / legal-contractual need | WhitePact database/monitoring | policy-defined audit period | hash-chained/tamper-evident evidence where applicable; minimize raw content |
| ROPA-05 | Customer-submitted evaluation content | prompts/text/model outputs; may incidentally contain personal data | return requested guardrail/trust/evaluation result | contract; customer controls source/authority | WhitePact app/database if retained; customer-configured model provider only where configured | short-lived/policy-defined result retention | minimization; avoid unnecessary evidence payloads; customer responsibility for submitted content |
| ROPA-06 | Public AI incident submissions | report details; optional reporter name/contact | operate moderated public AI incident registry | consent/legitimate interest subject to context | WhitePact database/public page for approved public fields | public incident record may be persistent; reporter contact remains non-public per policy | reporter identity/contact field protection; moderation before publication |
| ROPA-07 | Public trust/passport/leaderboard data | model/provider/trust result and organization attribution if intentionally supplied | public trust/transparency service | consent/contract/legitimate interest depending submitter | public WhitePact surfaces | according to product/public-registry policy | do not include unintended personal/confidential data |
| ROPA-08 | Billing | billing contact/transaction metadata | charge for paid services when offered | contract/legal obligation | Stripe or other approved payment provider | accounting/provider/legal retention | governance content should not be sent to billing provider |
| ROPA-09 | Security/privacy/support requests | requester contact and request/incident details | support, rights handling, security response | contract/legal obligation/legitimate interest | authorized WhitePact personnel/tools | according to request/incident retention needs | store sensitive request content outside public repo; least privilege |

\* Legal-basis labels are working internal assumptions for readiness. Qualified counsel should validate them for the actual customer/deployment/jurisdiction before WhitePact relies on them contractually.

## Data-flow boundaries

### Provider-hosted core flow

User/integrator → WhitePact application/API/MCP → authentication/authorization/governance → managed database/cache/infrastructure → response/evidence.

Current documented infrastructure/subprocessor baseline includes Render for compute, Supabase for PostgreSQL/data services and Upstash for Redis/rate-limit use, subject to the current vendor/DPA register.

### Customer identity flow

Customer identity provider → signed/asserted identity claims → WhitePact verification/mapping → organization/role context.

Customer controls identity lifecycle and provider-side group/user configuration; WhitePact controls its own validation/mapping and authorization boundary.

### Customer-configured model/provider flow

Customer request → WhitePact integration → external model/provider only if the customer enables/configures that integration.

Provider terms and data handling for that external model are a shared/customer dependency and must not be represented as a WhitePact-controlled guarantee.

### Public-feature flow

Submitter → WhitePact public feature → moderation/validation where applicable → selected fields become public by design.

Reporter/private contact fields must remain separated from public incident content.

## Data categories

- account/organization identifiers;
- contact information;
- authentication/security metadata;
- optional IP/network metadata;
- customer-submitted text/content;
- AI/model/provider metadata;
- public incident/trust information intentionally submitted for publication;
- billing metadata handled through approved payment provider;
- privacy/security/support correspondence.

WhitePact should not intentionally collect special-category/sensitive personal data unless a documented feature/customer use case requires it and a privacy/AI impact assessment has been completed.

## Data-subject categories

- customer administrators and users;
- developers/integrators;
- support/security/privacy requesters;
- optional incident reporters;
- individuals incidentally referenced in customer-submitted content.

## Subprocessor control

Canonical current list and contract posture live in `compliance/DPA_TEMPLATE.md` and `compliance/VENDOR_RISK_ASSESSMENT.md`. This RoPA must be updated when a new subprocessor materially changes processing.

Provider certifications are inherited/shared evidence only; they are not WhitePact certifications.

## International-transfer review

Actual transfer assessment depends on customer/user geography, deployment region, subprocessors and contract terms. Before an enterprise deployment creates a regulated cross-border transfer, record:

- exporter/importer roles;
- locations/regions;
- data categories;
- transfer mechanism/contractual safeguard if required;
- supplementary technical measures;
- counsel review where legal interpretation is material.

## Retention and deletion

Retention commitments are defined in `PRIVACY_POLICY.md`. Operating evidence for deletion should be tracked in `compliance/OPERATING_EVIDENCE_REGISTER.md`.

A written schedule is not proof of deletion. Where automation is absent or incomplete, use a documented manual procedure until technical enforcement exists and retain dated evidence.

## Review triggers

Update this RoPA when:

- adding a new hosted data store/vendor/subprocessor;
- adding a new category of personal/sensitive data;
- materially changing retention;
- introducing model training/fine-tuning using customer data;
- adding long-term agent memory or retrieval over personal data;
- introducing a new public-data surface;
- expanding to a new regulated geography/customer sector;
- materially changing support/telemetry/analytics collection.

## Claim boundary

This record demonstrates that WhitePact maintains a first-party processing inventory. It is not an attorney-approved legal conclusion about every deployment or jurisdiction.
