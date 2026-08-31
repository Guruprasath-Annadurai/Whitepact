# Public Trust Claims Policy

Last verified: 2026-08-31. Claims must identify their evidence boundary and must not turn
self-assessment, pipeline configuration, or vendor certification into WhitePact
certification.

## A. Officially awarded

- **OpenSSF Best Practices Silver** — BadgeApp project 14112 currently records Silver.
- **OSPS Baseline Level 1** — the same official project record currently awards Level 1.

Approved: “WhitePact is currently awarded OpenSSF Best Practices Silver and OSPS
Baseline Level 1 on project 14112.”

Do not call either an independent audit. Gold and OSPS L2/L3 are not awarded.

## B. Machine-verified technical evidence

Claims are allowed only with the specific run/release/commit:

- Python tests and 90% statement / 80% pure-branch CI gates.
- pinned GitHub Actions/container inputs and hash-locked security scanner tooling.
- SAST/SCA/dependency-review/Gitleaks results from named workflow runs.
- reproducible-build results, CycloneDX SBOM, artifact digests and GitHub attestations.
- signed annotated `v1.2.6` tag and approved signer verification.
- PyPI Trusted Publishing and builder/PyPI SHA-256 parity for `v1.2.6`.

Approved: “Release v1.2.6 was built and reproduced by WhitePact's reusable trusted
builder, published through PyPI Trusted Publishing without rebuilding, and its signed
tag, checksums, CycloneDX SBOM, provenance and SBOM attestation can be independently
checked.”

The `v1.2.6` wheel and sdist completed the hardened path and independently verified
against the expected repository, reusable workflow, source commit, signed tag ref and
GitHub-hosted runner. The recorded SLSA v1.2 assessment permits the scoped statement:
“WhitePact v1.2.6 release evidence satisfies SLSA v1.2 Build L3 requirements.” This is a
release-specific conformance assessment, not “SLSA certification,” a claim about every
WhitePact version, or proof that the artifact is free of vulnerabilities.

## C. Self-assessment / alignment

These may be described only as mappings, support or self-assessments:

- CAIQ v4.0.3 evidence-boundary self-assessment.
- NIST AI RMF 1.0 support mapping.
- EU AI Act technical-support mapping.
- ISO/IEC 42001 AIMS support matrix.
- OWASP LLM/Agentic risk mapping.
- internal security review and threat model.

Approved examples:

- “WhitePact provides technical controls mapped to the NIST AI RMF functions.”
- “WhitePact can support selected logging and human-oversight activities relevant to the
  EU AI Act; applicability and compliance remain the operator's legal responsibility.”
- “WhitePact has completed an internal, non-independent security review.”

## D. Not currently claimable

- OpenSSF Best Practices Gold or OSPS L2/L3 award.
- “SLSA certified,” any SLSA level for releases other than those individually assessed,
  or a claim that provenance guarantees artifact security.
- CSA STAR Level 1/2 registration, certification or attestation.
- ISO/IEC 42001, ISO 27001, SOC 2, NIST, OWASP, EU AI Act or CAIQ certification.
- “EU AI Act fully compliant.”
- independent penetration testing or independent security assessment.
- enterprise customers, customer deployments, revenue, uptime, regions, backups, DR, MFA
  enforcement or operational effectiveness without current evidence.
- inheritance of Render/Supabase/Upstash certifications as WhitePact certification.

Prohibited examples:

- “OpenSSF Gold certified.”
- “OSPS Level 3 achieved.”
- “SLSA certified” or an unscoped “WhitePact is SLSA L3” claim.
- “CSA STAR certified.”
- “ISO 42001 / NIST / OWASP / EU AI Act certified or fully compliant.”
- “Independently pentested” based on Bandit, ZAP, property tests or the internal review.

## Review rule

Before publishing a trust claim, link its official registry or immutable run/release
evidence, state the date/version, and check `WHITEPACT_TRUST_STATUS.md`. If a claim depends
on an owner, human, deployment, registry or auditor action, keep that blocker in the same
customer-facing context. Remove stale badges/claims promptly when evidence expires.
