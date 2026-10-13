# WhitePact Legal and Commercial Readiness Register

**Status:** First-party readiness inventory; not legal advice  
**Review date:** 2026-09-13  
**Owner:** WhitePact maintainer / service owner

## Purpose

Separate commercial documents WhitePact can prepare internally from actions that legitimately require qualified counsel, an insurer, a customer, a regulator, a certification body, or an authorized company representative.

## 1. Existing internal commercial/legal artifacts

| Artifact | Internal state | External step |
|---|---|---|
| `TERMS_OF_SERVICE.md` | Substantive draft/adopted operating text where stated | Qualified counsel review before relying on it for material enterprise contracting |
| `PRIVACY_POLICY.md` | Detailed operating policy; explicitly self-drafted | Counsel validation for jurisdiction-specific reliance |
| `compliance/DPA_TEMPLATE.md` | Detailed data-processing template | Counsel review + customer execution |
| `compliance/DPA_ATTORNEY_SCOPE_BRIEF.md` | Ready for efficient legal handoff | Attorney engagement |
| `SLA.md` | Service/availability commitments and architecture assumptions documented | Align final sold SLA with actual production capacity and customer contract |
| `ENTERPRISE_SECURITY.md` | Security posture/shareable buyer material | Update against exact release and external assurance as obtained |
| `compliance/VENDOR_RISK_ASSESSMENT.md` | Vendor/subprocessor assessment exists | Periodic revalidation and contractual/vendor evidence |
| `compliance/OEM_LICENSING.md` | Commercial/OEM readiness material exists | Negotiated customer/partner agreement and counsel review where material |
| `LICENSE` / MIT licensing | Public software license exists | Commercial proprietary modules/dual-licensing require deliberate future policy if introduced |

## 2. Internally completable contract-preparation work

WhitePact can maintain, without paid external assurance:

- current product/service description and scope;
- security architecture and shared-responsibility description;
- service-level objectives and support/escalation process;
- privacy/data-flow/subprocessor inventory;
- DPA draft and technical/organizational measures annex;
- security questionnaire/evidence pack;
- incident-notification operating procedure;
- acceptable-use/prohibited-use concepts where relevant;
- IP/open-source dependency/license inventory;
- pricing/order-form fields and commercial assumptions;
- customer onboarding/offboarding and credential-revocation process;
- exportable evidence/SBOM/provenance package;
- insurer questionnaire evidence package.

None of those internal drafts constitutes legal advice.

## 3. Attorney-only / external legal actions

WhitePact must not represent these as internally completed:

- legal opinion on GDPR/DPDP/EU AI Act applicability for a specific customer/use case;
- attorney-reviewed ToS/DPA/enterprise MSA;
- negotiation of liability caps, indemnity, warranty, IP infringement and governing-law language where material;
- cross-border transfer mechanism/legal assessment;
- sector-specific regulatory opinion (financial services, health, employment, government, etc.);
- trademark registration/legal clearance;
- litigation/regulator representation;
- determination that a customer deployment qualifies or does not qualify as a high-risk AI system under applicable law.

Internal engineering mappings may prepare counsel but do not replace counsel.

## 4. Authorized-officer/customer actions

Even when no lawyer is needed, ChatGPT/automation must not impersonate the company officer or customer for:

- signing attestations/declarations;
- accepting binding certification/registry terms;
- executing MSAs/DPAs/order forms;
- representing beneficial ownership/legal-entity facts that have not been verified;
- accepting customer-specific residual risk on behalf of a party lacking delegated authority;
- certifying facts to government/regulatory bodies.

The authorized WhitePact representative must perform or explicitly approve those acts.

## 5. Cyber/E&O insurance readiness

WhitePact can prepare evidence commonly requested during underwriting:

- business/product description;
- revenue/customer-stage information supplied by the owner;
- data categories and approximate volumes supplied/verified by the owner;
- security controls and MFA/SSO posture;
- incident history supplied/verified by the owner;
- vulnerability-management and patching process;
- backup/recovery procedures;
- vendor/subprocessor list;
- secure-development/release controls;
- independent pentest status stated truthfully;
- SOC/ISO/CSA status stated truthfully.

Policy quotation, underwriting decision, exclusions, premium and issuance are insurer/broker actions. WhitePact must not call itself insured until a policy is bound and in force.

## 6. Enterprise security questionnaire readiness

Default answer hierarchy:

1. Cite implemented technical evidence.
2. Cite an adopted operating policy where the question concerns process.
3. Identify inherited provider control and name the responsibility boundary.
4. Answer **No/Partial** where applicable controls are missing.
5. Answer **N/A** only with a role/scope rationale.
6. Never turn roadmap intent into **Yes**.
7. Never describe internal scans as independent penetration testing.
8. Never attribute a provider's SOC/ISO certification to WhitePact.

Canonical starting point: `compliance/ENTERPRISE_ASSURANCE_MASTER_INDEX.md`.

## 7. Commercial launch prerequisites vs enhancements

### Prerequisites for honest enterprise contracting

- stable/frozen product scope and exact release;
- security/privacy/service documentation matching reality;
- authorized contracting party and payment/invoicing capability;
- customer-specific scope/order terms;
- DPA where WhitePact processes customer personal data and one is required;
- incident/security contacts;
- ability to revoke/offboard customer access;
- accurate subprocessor list;
- explicit treatment of unsupported/experimental features.

### High-value enhancements, not universal legal prerequisites

- independent penetration test;
- SOC 2 report;
- ISO/IEC 27001 certificate;
- ISO/IEC 42001 certificate;
- CSA registry listings;
- cyber/E&O insurance;
- external privacy/security counsel review.

Large/regulated customers may make one or more enhancements contractual prerequisites even when law does not universally require them.

## 8. Claim boundary

Allowed now: **"WhitePact maintains enterprise legal/commercial drafts, security evidence and contract-preparation materials ready for external counsel/customer review."**

Not allowed without evidence: **"attorney approved," "fully legally compliant," "insured," "certified," or "contractually approved by enterprises."**
