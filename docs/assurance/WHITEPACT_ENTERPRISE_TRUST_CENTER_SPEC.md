# Enterprise Trust Center specification

Rule: a control appears as **Implemented**, **Tested**, **Independently verified**, **Self-attested**,
**Externally certified** or **Planned**. Today nothing is Independently verified or Externally certified. Pages only
publish what the status below supports. Internal evidence stays behind enterprise access; no secrets or
exploit-enabling detail are published.

| Section | Public content (supported now) | Status | Evidence in the repository |
| --- | --- | --- | --- |
| Security overview | doctrine, what is and is not enforced | Implemented, Tested | `docs/launch/ENFORCEMENT_PATH_MATRIX.md`, `docs/launch/AGENTIC_THREAT_REGISTER.md` |
| Architecture and supported deployments | control chain, isolation, evidence | Implemented | `docs/architecture/`, `Dockerfile.isolation`, `infra/` (prepared, never applied) |
| Authorization boundary | enforced vs advisory vs ungoverned paths; no claim on unmediated actions | Tested | matrix above |
| Identity and access | API keys, OIDC/SAML/SCIM, TOTP step-up (OIDC/WebAuthn step-up NOT supported) | Tested | `tests/test_step_up_forged_proofs_http.py` and others |
| Policy governance | attributed, hash-chained history; tiered model built, **off** | Tested (off) | `docs/launch/POLICY_CHANGE_GOVERNANCE_DECISION.md` |
| Evidence | hash chain, restore drill; **no external anchor** | Tested | `docs/launch/OPERATIONS_DRILL_REGISTER.md` |
| Data handling, retention, deletion | tenant erasure, classification of every table | Implemented, Tested | `data_governance/`, `tests/test_data_inventory.py` |
| Software supply chain | SLSA provenance and SBOM for releases; OSV results; VEX | Implemented, Self-verified | `WHITEPACT_SUPPLY_CHAIN_SECURITY_EVIDENCE.md` |
| Vulnerability reporting | private advisory form, maintainer email | Implemented | `SECURITY.md`; remediation policy is a **draft** |
| Incident response | runbooks | Implemented (documents), not drilled | `docs/security/AUTH_INCIDENT_RESPONSE.md` |
| Backup and recovery | local PostgreSQL drill only | Tested (disposable) | drill register; **no production DR** |
| Availability and capacity | one same-host benchmark; 1,000 concurrent connections NOT met | Measured | `docs/launch/HTTP_AUTHORIZATION_BENCHMARK.md` |
| Independent assessments | AI-agent audits only; no human pen test | Self-attested | handoff documents |
| Compliance status | none certified; mapping documents only | Planned | `WHITEPACT_CERTIFICATION_READINESS_MATRIX.md` |
| Known limitations | running tools are not cancelled by revocation; stdio is advisory; host-side fixture exception unreviewed; rate-limit cap (REC-28) | Disclosed | issue register |

Missing organizational controls: legal entity, DPA template, subprocessors list, customer support process and SLA, status page,
privacy impact assessment, data residency commitments, insurance. These are founder/legal items and are not drafted as facts.
