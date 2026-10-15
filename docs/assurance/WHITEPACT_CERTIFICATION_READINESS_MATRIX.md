# Certification and assurance readiness matrix

Facts about what each programme *is* are general knowledge of those programmes and were **not re-verified against
their current official texts in this pass**; costs and audit durations were **not verified** and are deliberately
left blank rather than guessed. Nothing here is a certification, attestation or audit.

| Programme | What it certifies / who issues it | Applies to WhitePact as | Honest status | Prerequisites not yet met |
| --- | --- | --- | --- | --- |
| OpenSSF Best Practices badge | self-attested criteria, publicly checkable | the open-source project | **silver (self-attested)**; 31 criteria open | see `WHITEPACT_OPENSSF_GAP_ANALYSIS.md`; gold needs a second maintainer and ≥ 90 % statement coverage evidence |
| OpenSSF Scorecard | automated repository-practice score | the repository | 7.4 on `main` (2026-10-06) | Signed-Releases, Fuzzing, Vulnerabilities, Contributors |
| OSPS Baseline | maturity-level controls, reported through the badge programme | the project | level-3 controls unmet (22 listed) | policies drafted (not adopted); QA-07.01 needs an independent human reviewer |
| ISO/IEC 27001 | an accredited certification body certifies an organization's ISMS for a stated scope | the *operating organization* and hosted service, not the repository | **not started**; no ISMS records | a legal entity (planned, not incorporated), risk register, internal audit, management review, months of operating evidence |
| ISO/IEC 42001 | accredited certification of an AI management system | the organization's AI governance process | not started | same organizational prerequisites; the product is a *tool for* such controls, not itself certified |
| SOC 2 (Type I / Type II) | a licensed CPA firm's attestation against Trust Services Criteria for a defined system | the hosted SaaS | not started; **no production service exists to attest** | production deployment, policies, evidence over an observation period (Type II) |
| Independent penetration test | a third party tests a stated scope | hosted service and/or release | **none commissioned**; Antigravity's reviews are an AI agent's audits and are not a pen test | budget, a stable candidate, scope agreement |
| Cyber Essentials (UK) | UK scheme for organizations | only if the operating organization is UK-based | not assessed | organization facts unknown |
| NIST CSF 2.0 / SSDF / AI RMF, OWASP ASVS / API Top 10 / agentic guidance, CSA CCM, CIS | guidance and control catalogues; **no certification exists** | design and review reference | partial mappings exist in docs; **no completed ASVS or CCM assessment** | an assessor and a scope |
| EU AI Act, GDPR, other law | legal obligations, not certifications | depends on the operator's role | **not assessed legally**; documents mapping to them are not compliance | legal advice |

**Highest value for the least money:** finish the OpenSSF items that need only documents and settings; commission one
independent penetration test of a frozen candidate; defer ISO 27001 / SOC 2 until there is an operating organization
and a production service. This is a recommendation for the founder, not a plan that has been approved.
