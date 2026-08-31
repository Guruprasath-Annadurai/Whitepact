# ISO/IEC 42001:2023 Support Matrix

ISO describes ISO/IEC 42001 as requirements for establishing, implementing, maintaining
and continually improving an organizational AI management system (AIMS), using a
Plan–Do–Check–Act approach (`https://www.iso.org/standard/42001`). The full standard is
copyrighted; this matrix maps public high-level management-system areas and does not
assert clause-level conformity.

WhitePact itself is **not ISO/IEC 42001 certified**. Certification requires an accredited
external audit of the organization's defined AIMS scope and operating evidence.

| AIMS support area | WhitePact capability/evidence | Status | Limitation / required organizational control |
|---|---|---|---|
| Context, scope and interested parties | intent/purpose records, org/agent inventory inputs | PARTIALLY SUPPORTED | organization defines AIMS boundary, stakeholders, needs and exclusions |
| Leadership and accountability | roles, governance cadence, accountable identity evidence | ORGANIZATIONAL CONTROL | one maintainer is not independent oversight; leadership commitment cannot be automated |
| AI policy and objectives | versioned policies, risk/authority configurations | PARTIALLY SUPPORTED | governing body approves measurable objectives and policy |
| Risk and opportunity assessment | risk tiers, threat model, compliance/evaluation engines | SUPPORTED | organization supplies use context, acceptance criteria and legal/ethical analysis |
| AI system impact assessment | evidence exports, bias/privacy/trust measurements | PARTIALLY SUPPORTED | affected-party impact assessment and sign-off remain organizational |
| Resources, competence and awareness | technical docs and support routes | ORGANIZATIONAL CONTROL | staffing, competence records and training are absent |
| Operational planning/control | authority ceilings, approval, quarantine, execution binding | SUPPORTED | deployment integration and configured controls determine effectiveness |
| Data management | PII guardrails, dataset/bias tooling, optional encryption | PARTIALLY SUPPORTED | lineage, quality, rights, retention and lifecycle policy remain organizational |
| Third-party/supply-chain management | vendor assessment, SBOM, Dependabot, SCA, VEX | PARTIALLY SUPPORTED | contracts, provider due diligence and service monitoring are owner duties |
| Monitoring/measurement/evaluation | tests, Prometheus, drift, evidence/outcome records | SUPPORTED | metrics need system-specific validation and operational retention |
| Internal audit | internal review and automated security scans | PARTIALLY SUPPORTED | not independent; formal audit programme/competence/cadence incomplete |
| Management review | quarterly governance cadence | ORGANIZATIONAL CONTROL | operating history and independent oversight are absent |
| Nonconformity/corrective action | issues/PRs, vulnerability/incident processes | PARTIALLY SUPPORTED | formal corrective-action register and effectiveness review needed |
| Continual improvement | versioned controls, regression tests, dependency updates | PARTIALLY SUPPORTED | management must evaluate trends, objectives and improvement outcomes |
| Certification | no accredited audit/certificate | EXTERNAL AUDIT REQUIRED | select certification body, define scope, operate AIMS and close audit findings |

Permitted wording: “WhitePact provides technical capabilities that can support an
organization's ISO/IEC 42001 AIMS.” It may not say certified, accredited, conformant, or
audit-ready without a scoped independent gap assessment and operating evidence.
