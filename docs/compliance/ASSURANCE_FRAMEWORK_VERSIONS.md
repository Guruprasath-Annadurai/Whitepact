# Assurance Framework Versions and Evidence Retrieval Registry

**Project:** WhitePact (`Guruprasath-Annadurai/Whitepact`)  
**Scope:** Zero-Cost Enterprise Trust, Open Source Security & Assurance Qualification Program  
**Audit Date / Refresh:** 2026-09-28  
**Status:** Living Evidence Register  

---

## 1. Normative Framework Versions

| Framework / Standard | Canonical Organization | Normative Version | Evaluation Date / Baseline | Project Identifier / Reference |
|---|---|---|---|---|
| **OpenSSF Best Practices Badge** | Open Source Security Foundation (Linux Foundation) | Current Criteria Schema (2026) | 2026-08-31 (Silver Awarded) | Project ID: `14112` |
| **OpenSSF OSPS Baseline** | Open Source Security Foundation | **v2026.08.28** | 2026-08-30 (L1 Awarded, L2/L3 Audited) | Official Checklist v2026.08.28 |
| **OpenSSF Scorecard** | OpenSSF / OpenSSF Supply Chain Working Group | **v5.5.0** | 2026-09-27 (Score: 8.1/10) | Public Scorecard API, commit `81beb3ac50e17068c7d6f26d9a07f2cb0442dbec` |
| **SLSA (Supply-chain Levels for Software Artifacts)** | OpenSSF SLSA Specification Committee | **v1.2 (Build Track)** | 2026-08-31 (Release `v1.2.6` verified) | Build L3 Reusable Workflow (`.github/workflows/reusable-build.yml`) |
| **CSA STAR Level 1 (CAIQ)** | Cloud Security Alliance | **CAIQ v4.0.3** | 2026-08-31 / 2026-09-28 | `compliance/CAIQv4.0.3_WhitePact_completed.xlsx` |
| **CSA AI-CAIQ (STAR for AI)** | Cloud Security Alliance / AI Safety Initiative | **AI-CAIQ v1.1** | 2026-09-28 | Official questionnaire migration required; the repository narrative is not a submission workbook |
| **CycloneDX SBOM** | OWASP CycloneDX Working Group | **v1.5 / JSON Schema** | 2026-08-31 (`v1.2.6`) | Attested release artifact `sbom.cyclonedx.json` |
| **OpenVEX** | OpenVEX Project (Linux Foundation) | **v0.2.0** | 2026-08-31 | `security/whitepact.openvex.json` |

---

## 2. Evidence Retrieval Timestamps and Authoritative Artifacts

### 2.1 OpenSSF Best Practices Badge (ID: 14112)
- **Official URL:** `https://bestpractices.coreinfrastructure.org/en/projects/14112`
- **Earned Level:** Silver (awarded 2026-08-31).
- **Gold Status:** Evaluated 2026-08-31 and 2026-09-28.
- **Authoritative Classification:** `TECHNICALLY_READY_BUT_HUMAN_BLOCKED`.
  - All 15 technical criteria satisfied and CI-enforced.
  - 3 criteria strictly `HUMAN_BLOCKED`: `bus_factor >= 2`, `contributors_unassociated >= 2`, `two_person_review >= 50%`.
  - 2 criteria `OWNER_ACTION_REQUIRED`: `require_2FA`, `secure_2FA` (GitHub account settings).
  - 1 criterion `EXTERNAL_SUBMISSION_REQUIRED`: `hardened_site` live verification submission.

### 2.2 OpenSSF OSPS Baseline (Version: 2026.08.28)
- **Checklist Version:** `2026.08.28` (retrieved officially on 2026-08-30).
- **Earned Level:** Level 1 awarded.
- **Level 2 Evaluation:** `ELIGIBLE / TECHNICALLY SATISFIED` (19/19 controls pass).
- **Level 3 Evaluation:** `NOT_YET_ELIGIBLE` due to control `OSPS-QA-07.01` (requires at least one non-author human approval prior to merge; cannot be satisfied by solo maintainer without manufacturing synthetic identities).

### 2.3 OpenSSF Scorecard (v5.5.0)
- **Public API result:** dated 2026-09-27 on commit `81beb3ac50e17068c7d6f26d9a07f2cb0442dbec`.
- **Score:** 8.1 / 10.
- **10/10 Scores:** `Security-Policy`, `Maintained`, `Binary-Artifacts`, `Code-Review`, `Dangerous-Workflow`, `Dependency-Update-Tool`, `Token-Permissions`, `License`, `SAST`, `Packaging`, `CI-Tests`.
- **Deductions Analyzed:**
  - `Branch-Protection`: Scanner API token limit (`Resource not accessible by integration`), verified locally as protected.
  - `Contributors`: `0/10` due to single primary contributor (`HUMAN_BLOCKED`).
  - `Pinned-Dependencies`: `5/10` (some dependencies are not hash-pinned).
  - `Signed-Releases`: `0/10` (Scorecard heuristic does not parse custom SSH signature + Rekor attestation pattern; cryptographically verified independently).
  - `Fuzzing`: `0/10` (Hypothesis property-based tests exist; external continuous fuzzing engine not yet integrated).
  - `Vulnerabilities`: `9/10` (one existing vulnerability reported; triage required).

### 2.4 SLSA v1.2 Build Track
- **Specification:** [SLSA v1.2 Specification](https://slsa.dev/spec/v1.2/)
- **Target Products:** Python Wheel (`whitepact-*.whl`) and Source Distribution (`whitepact-*.tar.gz`).
- **Target Release:** `v1.2.6` (commit `f784c44819c9c26f4e3486a9a6331508e20fd1eb`, tag SSH-signed by `milchcreamfoods@gmail.com`).
- **Builder:** Reusable workflow `.github/workflows/reusable-build.yml` on GitHub-hosted Ubuntu runner.
- **Attestation Predicate:** `https://slsa.dev/provenance/v1`.
- **Level Achieved:** SLSA v1.2 Build Level 3 (Build L3) verified via `gh attestation verify`.

### 2.5 CSA STAR Level 1 (CAIQ v4.0.3 & AI-CAIQ v1.1)
- **CAIQ Standard:** Consensus Assessment Initiative Questionnaire v4.0.3 (17 domains, 261 questions).
- **Status:** Self-Assessment Completed. Authoritative spreadsheet: `compliance/CAIQv4.0.3_WhitePact_completed.xlsx`.
- **AI Governance Profile:** The repository narrative in `docs/compliance/CSA_AI_CAIQ_SELF_ASSESSMENT.md` is a preliminary evidence map only. It must be migrated into the official AI-CAIQ v1.1 questionnaire before STAR for AI submission.
- **Registry Submission:** `OWNER_ACTION_REQUIRED` (free registry submission at Cloud Security Alliance STAR Registry).

---

## 3. Truth Boundaries & Anti-Gaming Covenant

1. **No Synthetic Identifiers:** WhitePact strictly refuses to manufacture mock contributors, dummy GitHub accounts, or synthetic PR approvals to falsely satisfy `bus_factor`, `contributors_unassociated`, or `two_person_review`.
2. **Distinction Between Architecture and Operation:** Self-hosted and deployable security features (Pydantic validation, hash-chained audit trails, role-based access control, cryptographic verification) are verified in source code; managed cloud infrastructure assertions (Render, Supabase, Upstash) are bounded by owner declarations and external probes.
3. **No Unwarranted Certification Claims:** Self-assessments (CAIQ, NIST CSF, ISO 42001 mapping) are explicitly labeled as internal self-assessments, NOT accredited third-party certifications.
