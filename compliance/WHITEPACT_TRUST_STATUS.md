# WhitePact Trust Status

Point-in-time master status: 2026-08-31. This file separates official awards, repository
implementation, release evidence, and external assurance.

| Area | Status | Verified evidence | Public claim allowed | Blocker | Next action |
|---|---|---|---|---|---|
| OpenSSF Best Practices | ACHIEVED | official project 14112 = Silver | “Silver awarded” | Gold human/account/official criteria | merge controls, update BadgeApp; earn real reviewer/contributor history |
| OpenSSF Scorecard | VERIFIED | official v5.0.0 score 4.2 on 2026-08-27 | exact dated score only | rescan after PR #52/this branch | merge and wait for official rescan |
| OSPS Baseline | ACHIEVED | official Level 1; current 2026.08.28 audit | “Level 1 awarded” | L3 non-author approval; release/owner evidence | submit updated L2 evidence; do not claim award early |
| SLSA | PENDING RELEASE VERIFICATION | hardened architecture on separate branch `c9bf6d6`; prior attestation evidence | implementation/pending language only | exact release not yet built/verified through new builder | merge SLSA work, release, run consumer verification |
| SBOM | VERIFIED | CycloneDX attached to v1.2.3 and workflow generation | named-release SBOM available | SBOM attestation/new-release association | verify exact next-release SBOM/digests |
| Signed release | VERIFIED | signed annotated v1.2.3 and approved SSH signer | v1.2.3 signed-tag claim | historical tags unsigned | keep all future tags signed and audit log current |
| PyPI Trusted Publishing | VERIFIED | v1.2.3 release record/workflow OIDC | named-release claim | next pipeline release | retain no long-lived token |
| Reproducible builds | TECHNICALLY READY | PR #52 reproducible workflow/tests | branch technical evidence | official main/new release evidence | merge and preserve required check |
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
