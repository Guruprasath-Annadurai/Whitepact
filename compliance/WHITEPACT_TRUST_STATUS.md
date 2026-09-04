# WhitePact Trust Status

Point-in-time master status: 2026-08-31. This file separates official awards, repository
implementation, release evidence, and external assurance.

| Area | Status | Verified evidence | Public claim allowed | Blocker | Next action |
|---|---|---|---|---|---|
| OpenSSF Best Practices | ACHIEVED | official project 14112 = Silver | “Silver awarded” | Gold human/account/official criteria | update BadgeApp evidence; earn real reviewer/contributor history |
| OpenSSF Scorecard | VERIFIED | official v5.0.0 score 6.1 on 2026-08-31 for `8f8ef53` | exact dated score only | Branch-Protection API error; human/history and scanner deductions | address legitimate technical deductions; wait for real history where required |
| OSPS Baseline | ACHIEVED | official Level 1; current 2026.08.28 audit | “Level 1 awarded” | L3 non-author approval; release/owner evidence | submit updated L2 evidence; do not claim award early |
| SLSA | VERIFIED (RELEASE-SPECIFIC) | v1.2.6 wheel/sdist verify against the main reusable builder, source commit/tag and hosted runner; v1.2 normative assessment recorded | “v1.2.6 release evidence satisfies SLSA v1.2 Build L3” with scope | not a certification or artifact-security guarantee | preserve builder and consumer verification on every release |
| SBOM | VERIFIED | v1.2.6 CycloneDX release asset, checksum and wheel-bound SBOM attestation | v1.2.6 SBOM/attestation available | SBOM describes dependencies; it is not a vulnerability-free claim | preserve generation, attestation and verification |
| Signed release | VERIFIED | approved-signer annotated `v1.2.6` tag verified locally and in run 33337718757 | v1.2.6 signed-tag claim | historical tags vary | keep all future tags signed and audit log current |
| PyPI Trusted Publishing | VERIFIED | v1.2.6 OIDC publication and PyPI hashes match builder outputs | named-release exact-byte claim | future releases require fresh evidence | retain no long-lived token |
| Reproducible builds | VERIFIED (RELEASE-SPECIFIC) | v1.2.6 builder's byte comparison passed | v1.2.6 reproducible-build claim | not independently rebuilt outside GitHub | preserve build-twice gate and consider external rebuild corroboration |
| Repository governance | TECHNICALLY READY | classic protection verified; PR/checks/no force/deletion | factual settings only | required-check refresh; no reviewer approval | owner updates checks; add real second reviewer when available |
| Internal security review | VERIFIED | dated internal review and threat model | “internal/non-independent review” | independent validation | commission scoped penetration test |
| Fuzz/property testing | VERIFIED | Hypothesis authority/identity/evidence suites | factual test claim | no continuous coverage-guided service | consider Atheris/CIFuzz only with meaningful harness |
| Vulnerability management | TECHNICALLY READY | PVR/Dependabot/secrets settings; policy/scans/VEX | documented process/technical controls | operating history and optional GitHub settings | merge, require scan, review exceptions quarterly |
| Hardened website | VERIFIED | dated public-edge HTTPS/header/TLS checks | exact observed results | cookies, legacy TLS, origin and sensitive routes | independent hosted-service test |
| CAIQ | VERIFIED | 261-row evidence-classified v4.0.3 self-assessment | “CAIQ self-assessment available” | owner assertions, STAR submission/assurance | owner review and external STAR process |
| NIST AI RMF | TECHNICALLY READY | four-function support mapping | “mapped/supports selected outcomes” | organizational operation/independent TEVV | deployer completes profile and risk process |
| EU AI Act | NOT CLAIMABLE | technical support mapping only | support wording only | legal classification/conformity/operation | counsel determines role/applicability and obligations |
| ISO/IEC 42001 | EXTERNAL AUDIT REQUIRED | AIMS support matrix | support wording only | organizational AIMS and accredited audit | scope, operate, internal-audit, management-review, certify |
| OWASP AI/Agentic | TECHNICALLY READY | ASI/LLM mapping with code/tests | “mapped to selected risks” | not a certification; residual controls | validate deployment and keep mapping current |
| Independent penetration test | EXTERNAL AUDIT REQUIRED | none performed | must say none | independent assessor/funding/scope | test application, MCP/OAuth/tenant/cloud boundaries and remediate |

Use only the status vocabulary in this table. A branch can be technically ready while an
official badge or released artifact remains unverified; those are not contradictions.
