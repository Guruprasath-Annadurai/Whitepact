"""Answer set for the CSA STAR Level 1 CAIQ v4.0.3 questionnaire,
grounded in the real, current state of the WhitePact/ResponsibleAI
codebase and its existing compliance docs (compliance/CAIQ_SELF_ASSESSMENT.md,
THREAT_MODEL.md, SOC2_READINESS.md, ENTERPRISE_SECURITY.md,
compliance/KEY_MANAGEMENT.md, GOVERNANCE.md, compliance/INTERNAL_SECURITY_REVIEW.md,
compliance/INCIDENT_RESPONSE_RUNBOOK.md, DEPLOY_RUNBOOK.md).

Answer tuple: (answer, ownership, description)
  answer:    "Yes" | "No" | "NA"
  ownership: "CSP-owned" | "CSC-owned" | "3rd-party outsourced" |
             "Shared CSP and CSC" | "Shared CSP and 3rd-party"
  description: short, honest, cites the real file/mechanism (or states
               plainly that the control doesn't exist yet)

CSP = WhitePact (the org filling out this form). CSC = WhitePact's own
customers. "3rd-party" = the underlying infrastructure vendors
(Render/Supabase/Upstash) WhitePact runs on -- WhitePact operates no
physical infrastructure of its own.
"""

from __future__ import annotations

NO_FORMAL_ANNUAL_REVIEW = (
    "No formal annual review cadence yet -- solo-founder team, policies are "
    "updated as the codebase changes rather than on a calendar. See GOVERNANCE.md."
)

ANSWERS: dict[str, tuple[str, str, str]] = {}


def _set(qid: str, answer: str, ownership: str, desc: str) -> None:
    ANSWERS[qid] = (answer, ownership, desc)


# ── Audit & Assurance ────────────────────────────────────────────────
_set(
    "A&A-01.1",
    "Yes",
    "CSP-owned",
    "Documented in compliance/INTERNAL_SECURITY_REVIEW.md and THREAT_MODEL.md; "
    "not a formally separate 'audit and assurance' policy document.",
)
_set("A&A-01.2", "No", "CSP-owned", NO_FORMAL_ANNUAL_REVIEW)
_set(
    "A&A-02.1",
    "No",
    "3rd-party outsourced",
    "No independent third-party audit performed yet -- see "
    "compliance/NO_BUDGET_TRUST_PATH.md for the honest interim path "
    "(self-conducted scans, OpenSSF Scorecard) while SOC 2/pentest funding is pending.",
)
_set("A&A-03.1", "No", "CSP-owned", "No formal risk-based audit plan exists yet.")
_set(
    "A&A-04.1",
    "Yes",
    "CSP-owned",
    "Compliance mappings for AI-governance regulations (EU AI Act, NIST AI RMF, ISO 42001) "
    "are a product feature (rai_compliance, rai_eu_ai_act_classify tools); the platform's "
    "own infosec compliance status against those is tracked in compliance/SOC2_READINESS.md.",
)
_set(
    "A&A-05.1",
    "Yes",
    "CSP-owned",
    ".github/workflows/security-scan.yml (Bandit + pip-audit, weekly) + "
    "compliance/INTERNAL_SECURITY_REVIEW.md is the current audit-management process; "
    "informal, not a documented multi-step SOP.",
)
_set(
    "A&A-06.1",
    "Yes",
    "CSP-owned",
    "Findings are tracked and remediated via normal git issue/PR flow -- e.g. the nltk "
    "PYSEC-2026-597 fix documented in CHANGELOG.md. No separate formal 'corrective action plan' doc.",
)
_set(
    "A&A-06.2",
    "No",
    "CSP-owned",
    "No formal stakeholder reporting process -- solo founder is the only stakeholder today.",
)

# ── Application & Interface Security ─────────────────────────────────
_set(
    "AIS-01.1",
    "Yes",
    "CSP-owned",
    "CONTRIBUTING.md + THREAT_MODEL.md; ruff/mypy strict gate every commit via .github/workflows/ci.yml.",
)
_set("AIS-01.2", "No", "CSP-owned", NO_FORMAL_ANNUAL_REVIEW)
_set(
    "AIS-02.1",
    "Yes",
    "CSP-owned",
    "Pydantic request models with explicit field constraints on every REST endpoint "
    "(dashboard/app.py); parameterized SQL throughout (SQLAlchemy Core, no raw string interpolation).",
)
_set(
    "AIS-03.1",
    "Yes",
    "CSP-owned",
    "whitepact_* and rai_* Prometheus metrics (dashboard/prometheus.py) -- decision counters, "
    "evaluation latency, cost/usage; performance benchmarks in BENCHMARKS.md.",
)
_set(
    "AIS-04.1",
    "Yes",
    "CSP-owned",
    "PR-based flow: CI (ruff, mypy, pytest, 1723+ tests) required before merge, branch "
    "protection on main (4 required status checks). No formally documented SDLC policy doc.",
)
_set(
    "AIS-05.1",
    "Yes",
    "CSP-owned",
    "pytest suite (1723+ tests) gates every change; new features require passing tests before merge.",
)
_set(
    "AIS-05.2", "Yes", "CSP-owned", "Fully automated via .github/workflows/ci.yml on every push/PR."
)
_set(
    "AIS-06.1",
    "Yes",
    "CSP-owned",
    "Signed SBOM (CycloneDX) + Sigstore build provenance attestation on every release "
    "(RELEASING.md); PyPI trusted publishing (OIDC, no stored tokens).",
)
_set(
    "AIS-06.2",
    "Yes",
    "CSP-owned",
    ".github/workflows/publish.yml -- fully automated release pipeline.",
)
_set(
    "AIS-07.1",
    "Yes",
    "CSP-owned",
    "dependency-review.yml blocks vulnerable dependencies at PR time; security-scan.yml "
    "(Bandit + pip-audit) runs weekly. Real precedent: nltk PYSEC-2026-597, CHANGELOG.md.",
)
_set(
    "AIS-07.2",
    "Yes",
    "CSP-owned",
    "Dependency vulnerability detection is automated; remediation (the actual code fix) is manual.",
)

# ── Business Continuity Management and Operational Resilience ────────
_set(
    "BCR-01.1",
    "Yes",
    "Shared CSP and 3rd-party",
    "DEPLOY_RUNBOOK.md documents failover/recovery; underlying infra HA is inherited from "
    "Render/Supabase/Upstash's own resilience commitments.",
)
_set("BCR-01.2", "No", "CSP-owned", NO_FORMAL_ANNUAL_REVIEW)
_set(
    "BCR-02.1",
    "No",
    "CSP-owned",
    "No formal business-impact-analysis-driven strategy document -- informal, single-founder scale.",
)
_set(
    "BCR-03.1",
    "Yes",
    "Shared CSP and 3rd-party",
    "Documented in DEPLOY_RUNBOOK.md's DB failover section; relies on managed-provider redundancy, not self-operated multi-region.",
)
_set(
    "BCR-04.1",
    "No",
    "CSP-owned",
    "No formal resilience-strategy sign-off process; solo founder makes and documents the call directly.",
)
_set("BCR-05.1", "Yes", "CSP-owned", "DEPLOY_RUNBOOK.md, compliance/INCIDENT_RESPONSE_RUNBOOK.md.")
_set(
    "BCR-05.2",
    "Yes",
    "CSP-owned",
    "All documentation lives in the public GitHub repo, available to any authorized reviewer.",
)
_set("BCR-05.3", "No", "CSP-owned", NO_FORMAL_ANNUAL_REVIEW)
_set(
    "BCR-06.1",
    "No",
    "CSP-owned",
    "One tabletop exercise conducted (compliance/TABLETOP_EXERCISE_2026-07-21.md) -- not yet an "
    "annual/recurring practice.",
)
_set(
    "BCR-07.1",
    "No",
    "CSP-owned",
    "No CSC base yet to establish this with in practice; the runbook process would notify via the documented incident channel.",
)
_set(
    "BCR-08.1",
    "Yes",
    "3rd-party outsourced",
    "Managed PostgreSQL backups via Supabase; not self-operated backup infrastructure.",
)
_set(
    "BCR-08.2",
    "Yes",
    "Shared CSP and 3rd-party",
    "Field-level encryption (compliance/KEY_MANAGEMENT.md) protects specific PII columns "
    "independent of backup mechanism; backup confidentiality/integrity otherwise inherited from Supabase.",
)
_set(
    "BCR-08.3",
    "No",
    "3rd-party outsourced",
    "Restore capability exists via Supabase's own tooling; not independently tested/verified by us yet.",
)
_set("BCR-09.1", "Yes", "CSP-owned", "compliance/INCIDENT_RESPONSE_RUNBOOK.md.")
_set("BCR-09.2", "No", "CSP-owned", NO_FORMAL_ANNUAL_REVIEW)
_set("BCR-10.1", "No", "CSP-owned", "One tabletop exercise conducted (2026-07-21), not yet annual.")
_set(
    "BCR-10.2",
    "NA",
    "CSP-owned",
    "Not applicable -- no physical facility of our own; nothing for local emergency authorities to be included in.",
)
_set(
    "BCR-11.1",
    "NA",
    "3rd-party outsourced",
    "Not applicable -- WhitePact operates no physical equipment; fully on managed cloud PaaS.",
)

# ── Change Control and Configuration Management ──────────────────────
_set(
    "CCC-01.1",
    "Yes",
    "CSP-owned",
    "CONTRIBUTING.md + PR-based review flow; git history is the change record.",
)
_set("CCC-01.2", "No", "CSP-owned", NO_FORMAL_ANNUAL_REVIEW)
_set(
    "CCC-02.1",
    "Yes",
    "CSP-owned",
    "Branch protection on main (4 required status checks: ruff, mypy, pytest, dependency-review); "
    "no direct pushes without passing CI.",
)
_set(
    "CCC-03.1",
    "Yes",
    "CSP-owned",
    "Every change is a reviewable, tracked git PR/commit; risk is assessed via code review, not a formal risk register.",
)
_set(
    "CCC-04.1",
    "Yes",
    "CSP-owned",
    "Branch protection + required PR review prevents unauthorized direct changes to main.",
)
_set(
    "CCC-05.1",
    "NA",
    "CSC-owned",
    "Not applicable in current form -- no live multi-tenant hosted SaaS tier with customer-initiated change requests yet.",
)
_set(
    "CCC-06.1",
    "Yes",
    "CSP-owned",
    "main branch + required CI checks is the baseline; every release is tagged (see RELEASING.md).",
)
_set(
    "CCC-07.1",
    "Yes",
    "CSP-owned",
    "CI fails loudly (ruff/mypy/pytest) on any deviation from the established baseline before merge is possible.",
)
_set(
    "CCC-08.1",
    "No",
    "CSP-owned",
    "No formally documented emergency-change exception process -- informal, solo-founder judgment call today.",
)
_set(
    "CCC-08.2",
    "NA",
    "CSP-owned",
    "No formal GRC-04 policy-exception process exists yet to align with.",
)
_set(
    "CCC-09.1",
    "Yes",
    "CSP-owned",
    "git revert / redeploy previous tagged release is the rollback mechanism; not a formally documented automated rollback procedure.",
)

# ── Cryptography, Encryption & Key Management ─────────────────────────
_set(
    "CEK-01.1",
    "Yes",
    "CSP-owned",
    "compliance/KEY_MANAGEMENT.md documents the encryption approach and key-custody procedure.",
)
_set("CEK-01.2", "No", "CSP-owned", NO_FORMAL_ANNUAL_REVIEW)
_set(
    "CEK-02.1",
    "Yes",
    "CSP-owned",
    "Solo founder holds sole responsibility -- documented in compliance/KEY_MANAGEMENT.md, not a multi-person RACI.",
)
_set(
    "CEK-03.1",
    "Yes",
    "Shared CSP and 3rd-party",
    "At-rest: EncryptedString (Fernet/AES-128-CBC+HMAC via the `cryptography` package) for "
    "PII columns (db/encryption.py). In-transit: TLS terminated by Render/Supabase/Upstash.",
)
_set(
    "CEK-04.1",
    "Yes",
    "CSP-owned",
    "Fernet (authenticated symmetric encryption) applied specifically to PII/secret columns "
    "(audit_log.ip_address, mfa_secret, webhook secrets, reporter PII, upstream server auth_token, "
    "approval arguments) -- see db/engine.py's EncryptedString usage.",
)
_set(
    "CEK-05.1",
    "Yes",
    "CSP-owned",
    "Same PR/CI review process as all other code changes; no crypto-specific separate process.",
)
_set(
    "CEK-06.1",
    "Yes",
    "CSP-owned",
    "Standard git PR review + full test suite; no crypto-specific change board.",
)
_set(
    "CEK-07.1",
    "No",
    "CSP-owned",
    "No formal, separately-documented crypto risk program -- covered informally within THREAT_MODEL.md.",
)
_set(
    "CEK-08.1",
    "No",
    "CSC-owned",
    "Customers do not currently manage their own encryption keys -- RAI_FIELD_ENCRYPTION_KEY is operator-controlled.",
)
_set("CEK-09.1", "No", "CSP-owned", "No independent third-party audit of crypto systems yet.")
_set(
    "CEK-09.2",
    "No",
    "CSP-owned",
    "Not yet audited on a recurring cadence -- see compliance/NO_BUDGET_TRUST_PATH.md for the interim path.",
)
_set(
    "CEK-10.1",
    "Yes",
    "CSP-owned",
    "Python's `cryptography` library (Fernet.generate_key(), industry-standard, uses os.urandom "
    "under the hood) -- see db/encryption.py and compliance/KEY_MANAGEMENT.md.",
)
_set(
    "CEK-11.1",
    "Yes",
    "CSP-owned",
    "Each encrypted column uses the same Fernet/MultiFernet key set for a single, well-defined purpose (field encryption).",
)
_set(
    "CEK-12.1",
    "No",
    "CSP-owned",
    "No automatic time-based rotation policy -- rotation is manual, documented in compliance/KEY_MANAGEMENT.md.",
)
_set(
    "CEK-13.1",
    "Yes",
    "CSP-owned",
    "MultiFernet key-list rotation: new key placed first, old key(s) kept for decrypt-only until "
    "scripts/rotate_field_encryption_key.py re-encrypts existing rows, documented in compliance/KEY_MANAGEMENT.md.",
)
_set(
    "CEK-14.1",
    "Yes",
    "CSP-owned",
    "Old keys are dropped from RAI_FIELD_ENCRYPTION_KEY once the rotation sweep completes (compliance/KEY_MANAGEMENT.md).",
)
_set(
    "CEK-15.1",
    "NA",
    "CSP-owned",
    "Not applicable -- no pre-activation key state concept in the current Fernet/MultiFernet scheme.",
)
_set(
    "CEK-16.1",
    "No",
    "CSP-owned",
    "No formal key-transition approval workflow -- single-operator key custody today.",
)
_set(
    "CEK-17.1",
    "NA",
    "CSP-owned",
    "Not applicable -- Fernet keys used here have no built-in expiration-date concept; rotation is manual/event-driven.",
)
_set(
    "CEK-18.1",
    "No",
    "CSP-owned",
    "No separate archived-key repository; retired keys are removed from the active key list per compliance/KEY_MANAGEMENT.md's rotation procedure.",
)
_set(
    "CEK-19.1",
    "NA",
    "CSP-owned",
    "Not applicable -- no defined scenario for intentionally using a known-compromised key.",
)
_set(
    "CEK-20.1",
    "No",
    "CSP-owned",
    "No formal documented risk-assessment process for this specific tradeoff.",
)
_set(
    "CEK-21.1",
    "No",
    "CSP-owned",
    "Key lifecycle events (rotation) are manual and documented in compliance/KEY_MANAGEMENT.md, not machine-tracked/reported.",
)

# ── Datacenter Security ────────────────────────────────────────────────
# WhitePact operates no physical facility of its own -- entirely on managed
# PaaS (Render/Supabase/Upstash). Physical security is fully inherited.
_DCS_NA = "Not applicable -- WhitePact operates no physical premises/datacenter of its own; entirely on managed cloud PaaS (Render/Supabase/Upstash)."
for _qid in [
    "DCS-01.1",
    "DCS-01.2",
    "DCS-01.3",
    "DCS-02.1",
    "DCS-02.2",
    "DCS-02.3",
    "DCS-03.1",
    "DCS-03.2",
    "DCS-04.1",
    "DCS-04.2",
    "DCS-05.1",
    "DCS-06.1",
    "DCS-07.1",
    "DCS-07.2",
    "DCS-08.1",
    "DCS-09.1",
    "DCS-09.2",
    "DCS-10.1",
    "DCS-11.1",
    "DCS-12.1",
    "DCS-13.1",
    "DCS-14.1",
    "DCS-15.1",
]:
    _set(
        _qid,
        "No",
        "3rd-party outsourced",
        _DCS_NA
        + " See compliance/VENDOR_RISK_ASSESSMENT.md for each vendor's own physical-security posture.",
    )

# ── Data Security and Privacy Lifecycle Management ────────────────────
_set(
    "DSP-01.1",
    "Yes",
    "CSP-owned",
    "PRIVACY_POLICY.md + ENTERPRISE_SECURITY.md's Data Classification section (drafted, not yet attorney-reviewed).",
)
_set("DSP-01.2", "No", "CSP-owned", NO_FORMAL_ANNUAL_REVIEW)
_set(
    "DSP-02.1",
    "No",
    "3rd-party outsourced",
    "Storage-media disposal is inherited from Supabase/Render's own infrastructure lifecycle -- not directly controlled.",
)
_set(
    "DSP-03.1",
    "Yes",
    "CSP-owned",
    "PII columns are explicitly enumerated (compliance/KEY_MANAGEMENT.md's 'Columns currently using "
    "EncryptedString' list) -- a real, current inventory, not a separate formal data-inventory document.",
)
_set(
    "DSP-04.1",
    "Yes",
    "CSP-owned",
    "PII vs. non-PII is distinguished at the schema level (EncryptedString columns vs. plain columns); no formal multi-tier classification scheme beyond that.",
)
_set(
    "DSP-05.1",
    "No",
    "CSP-owned",
    "No formal data-flow diagram document exists yet -- THREAT_MODEL.md documents trust boundaries but not a full data-flow map.",
)
_set("DSP-05.2", "No", "CSP-owned", NO_FORMAL_ANNUAL_REVIEW)
_set(
    "DSP-06.1",
    "No",
    "CSP-owned",
    "No formal data-stewardship-ownership document -- solo founder is the de facto owner of all data.",
)
_set("DSP-06.2", "No", "CSP-owned", NO_FORMAL_ANNUAL_REVIEW)
_set(
    "DSP-07.1",
    "Yes",
    "CSP-owned",
    "Security-by-design is the whole point of the v3 authority-layer governance pipeline "
    "(SPEC.md) -- fail-closed evidence writes, execution-binding invariants, SSRF guards.",
)
_set(
    "DSP-08.1",
    "Yes",
    "CSP-owned",
    "Field-level encryption, redaction (GuardrailsEngine PII detection/redaction), argument-value exclusion from approval to_dict() responses.",
)
_set(
    "DSP-08.2",
    "Yes",
    "CSP-owned",
    "RAI_FIELD_ENCRYPTION_KEY unset = passthrough by design, but the PII/redaction guardrails and RBAC defaults are secure-by-default regardless.",
)
_set(
    "DSP-09.1",
    "No",
    "CSP-owned",
    "No formal DPIA process/document exists yet -- PRIVACY_POLICY.md covers the substance informally.",
)
_set(
    "DSP-10.1",
    "Yes",
    "Shared CSP and 3rd-party",
    "TLS in transit (hosting-provider terminated); Fernet encryption for specific PII fields at rest and in DB backups.",
)
_set(
    "DSP-11.1",
    "No",
    "CSP-owned",
    "No self-service data-subject-access-request (DSAR) API/UI exists yet; would be handled manually today.",
)
_set(
    "DSP-12.1",
    "Yes",
    "CSP-owned",
    "PRIVACY_POLICY.md states processing purposes; drafted, not yet attorney-reviewed for full regulatory alignment.",
)
_set(
    "DSP-13.1",
    "Yes",
    "CSP-owned",
    "compliance/DPA_TEMPLATE.md governs sub-processing terms; drafted, not yet attorney-reviewed or executed with a real customer.",
)
_set(
    "DSP-14.1",
    "No",
    "CSP-owned",
    "No automated per-CSC data-flow disclosure mechanism exists yet -- would be handled contractually/manually.",
)
_set(
    "DSP-15.1",
    "Yes",
    "CSP-owned",
    "No production data is copied into non-production/test environments -- tests use synthetic fixtures and in-memory SQLite exclusively.",
)
_set(
    "DSP-16.1",
    "No",
    "CSP-owned",
    "No formally documented data-retention/deletion schedule exists yet beyond what PRIVACY_POLICY.md states.",
)
_set(
    "DSP-17.1",
    "Yes",
    "CSP-owned",
    "Field-level encryption + redaction + hash-chained evidence with argument-value exclusion cover the sensitive-data lifecycle within the governance pipeline specifically.",
)
_set(
    "DSP-18.1",
    "No",
    "CSP-owned",
    "No documented law-enforcement-request-handling procedure exists yet -- would be handled ad hoc with legal counsel once retained.",
)
_set(
    "DSP-18.2",
    "NA",
    "CSP-owned",
    "Not applicable -- no such procedure exists yet to describe a notification-exception carve-out for.",
)
_set(
    "DSP-19.1",
    "Yes",
    "3rd-party outsourced",
    "compliance/CAIQ_SELF_ASSESSMENT.md's hosting-provider section documents the actual data locations (Render/Supabase/Upstash regions) as of the last review.",
)

# ── Governance, Risk and Compliance ────────────────────────────────────
_set(
    "GRC-01.1",
    "Yes",
    "CSP-owned",
    "GOVERNANCE.md documents the current (solo-founder) governance model plainly, including its real limitations.",
)
_set("GRC-01.2", "No", "CSP-owned", NO_FORMAL_ANNUAL_REVIEW)
_set(
    "GRC-02.1",
    "No",
    "CSP-owned",
    "No formal enterprise risk management (ERM) program exists yet -- risk is assessed informally per-feature (THREAT_MODEL.md) rather than org-wide.",
)
_set("GRC-03.1", "No", "CSP-owned", NO_FORMAL_ANNUAL_REVIEW)
_set("GRC-04.1", "No", "CSP-owned", "No formal policy-exception process exists yet.")
_set(
    "GRC-05.1",
    "Yes",
    "CSP-owned",
    "THREAT_MODEL.md + ENTERPRISE_SECURITY.md + the governance-core codebase itself constitute the information security program, even though it isn't organized as one single formal document.",
)
_set(
    "GRC-06.1",
    "Yes",
    "CSP-owned",
    "GOVERNANCE.md states plainly that the founder holds all roles today -- a real, honest answer, not a fabricated RACI matrix.",
)
_set(
    "GRC-07.1",
    "Yes",
    "CSP-owned",
    "compliance/SOC2_READINESS.md maps AICPA Trust Services Criteria against current reality; GDPR/CCPA-relevant terms drafted in PRIVACY_POLICY.md.",
)
_set(
    "GRC-08.1",
    "No",
    "CSP-owned",
    "No formal ongoing relationship with cloud-security special interest groups yet; this CAIQ submission and CSA STAR registration is the first step toward that.",
)

# ── Human Resources ─────────────────────────────────────────────────
# Solo-founder company -- most formal HR process controls honestly don't exist.
_set(
    "HRS-01.1",
    "No",
    "CSP-owned",
    "No employees/contractors yet -- solo founder. Background-verification policy will be built when hiring starts.",
)
_set(
    "HRS-01.2",
    "NA",
    "CSP-owned",
    "Not applicable -- no such policy exists yet to be jurisdiction-aligned.",
)
_set("HRS-01.3", "NA", "CSP-owned", "Not applicable -- no such policy exists yet.")
_set(
    "HRS-02.1",
    "No",
    "CSP-owned",
    "No formal acceptable-use policy document exists yet -- solo founder, informal practice only.",
)
_set("HRS-02.2", "NA", "CSP-owned", "Not applicable -- no such policy exists yet.")
_set(
    "HRS-03.1",
    "No",
    "CSP-owned",
    "No formal clean-desk/unattended-workspace policy document -- informal practice, home-based work.",
)
_set("HRS-03.2", "NA", "CSP-owned", "Not applicable -- no such policy exists yet.")
_set(
    "HRS-04.1",
    "No",
    "CSP-owned",
    "No formal remote-work-security policy document -- informal practice today.",
)
_set("HRS-04.2", "NA", "CSP-owned", "Not applicable -- no such policy exists yet.")
_set(
    "HRS-05.1",
    "NA",
    "CSP-owned",
    "Not applicable -- no employees/asset-return scenario exists yet.",
)
_set("HRS-06.1", "NA", "CSP-owned", "Not applicable -- no employees yet.")
_set("HRS-07.1", "NA", "CSP-owned", "Not applicable -- no employees yet.")
_set("HRS-08.1", "NA", "CSP-owned", "Not applicable -- no employment agreements exist yet.")
_set(
    "HRS-09.1",
    "Yes",
    "CSP-owned",
    "CONTRIBUTING.md + GOVERNANCE.md document the (currently solo) role and its security responsibilities.",
)
_set(
    "HRS-10.1",
    "No",
    "CSP-owned",
    "No standard NDA template in active use yet -- would be drafted with counsel before the first hire/contractor.",
)
_set(
    "HRS-11.1",
    "No",
    "CSP-owned",
    "No formal security-awareness training program exists yet -- solo founder, informal continuous learning only.",
)
_set("HRS-11.2", "NA", "CSP-owned", "Not applicable -- no such program exists yet.")
_set(
    "HRS-12.1",
    "NA",
    "CSP-owned",
    "Not applicable -- no employees beyond the founder, who has full context on the codebase by definition.",
)
_set("HRS-12.2", "NA", "CSP-owned", "Not applicable.")
_set(
    "HRS-13.1",
    "Yes",
    "CSP-owned",
    "GOVERNANCE.md and CONTRIBUTING.md are the current, real documentation of roles/policies -- read directly, not delivered via a formal training program.",
)

# ── Identity & Access Management ──────────────────────────────────────
_set(
    "IAM-01.1",
    "Yes",
    "CSP-owned",
    "RBAC model (rbac/models.py, rbac/permissions.py) with VIEWER/ANALYST/ADMIN/OWNER roles; documented in ENTERPRISE_SECURITY.md.",
)
_set("IAM-01.2", "No", "CSP-owned", NO_FORMAL_ANNUAL_REVIEW)
_set(
    "IAM-02.1",
    "Yes",
    "Shared CSP and CSC",
    "API keys are generated with cryptographically strong random values (not user-chosen passwords) and hashed (SHA-256) before storage.",
)
_set("IAM-02.2", "No", "CSP-owned", NO_FORMAL_ANNUAL_REVIEW)
_set(
    "IAM-03.1",
    "Yes",
    "CSP-owned",
    "org_api_keys table tracks role, org_id, creation/revocation state; reviewable via GET /api/orgs/{id}/keys.",
)
_set(
    "IAM-04.1",
    "Yes",
    "CSP-owned",
    "Role hierarchy (VIEWER < ANALYST < ADMIN < OWNER) enforces separation for privileged actions like approval resolution (ADMIN+) vs. read-only access (VIEWER+).",
)
_set(
    "IAM-05.1",
    "Yes",
    "CSP-owned",
    "Least privilege is a core design principle of the v3 authority-layer governance pipeline -- "
    "AuthorityContext.granted_action_types is per-action, not a blanket grant; role-gated REST endpoints throughout dashboard/app.py.",
)
_set(
    "IAM-06.1",
    "Yes",
    "CSP-owned",
    "POST /api/orgs/{id}/keys provisions a new key with an explicit role; every provisioning event is a normal, logged API call.",
)
_set(
    "IAM-07.1",
    "Yes",
    "CSP-owned",
    "DELETE /api/orgs/{id}/keys/{key_id} revokes immediately -- checked on every authenticate() call, not cached.",
)
_set(
    "IAM-08.1",
    "No",
    "CSP-owned",
    "No automated periodic access-review process exists yet -- access review is manual/ad hoc.",
)
_set(
    "IAM-09.1",
    "Yes",
    "CSP-owned",
    "ADMIN-role-gated actions (resolving approvals, managing policy rules, upstream server registration) are structurally separated from ANALYST-role read/call actions via require_role().",
)
_set(
    "IAM-10.1",
    "No",
    "CSP-owned",
    "No time-boxed/temporary elevated-access mechanism exists yet -- roles are persistent until explicitly changed/revoked.",
)
_set("IAM-10.2", "NA", "CSP-owned", "Not applicable -- no such time-boxed mechanism exists yet.")
_set(
    "IAM-11.1",
    "No",
    "CSC-owned",
    "No customer-participatory high-risk-access-grant workflow exists yet beyond the ADMIN-role resolve/approve mechanism itself.",
)
_set(
    "IAM-12.1",
    "Yes",
    "CSP-owned",
    "audit_log and governance_evidence are hash-chained and write-once by design (EvidenceRepository.record() has no update/delete method) -- structurally, not just by convention.",
)
_set(
    "IAM-12.2",
    "NA",
    "CSP-owned",
    "Not applicable -- there is no 'disable read-only' configuration; the write-once property is structural (no update/delete API exists), not a toggleable setting.",
)
_set(
    "IAM-13.1",
    "Yes",
    "CSP-owned",
    "Every API key is a unique, individually identifiable credential (org_api_keys.id); every AgentContext/IdentityContext carries a distinct identity_id used throughout the audit trail.",
)
_set(
    "IAM-14.1",
    "Yes",
    "CSP-owned",
    "Bearer API-key auth on every endpoint; optional TOTP-based MFA (auth/mfa.py, RFC 6238) enforceable at the org level; OIDC/OAuth resource-server support for SSO-issued JWTs.",
)
_set(
    "IAM-14.2",
    "No",
    "CSP-owned",
    "No client-certificate-based system-identity authentication exists yet -- Bearer tokens/API keys are the current mechanism.",
)
_set(
    "IAM-15.1",
    "Yes",
    "CSP-owned",
    "API keys are never stored in plaintext (SHA-256 hash only, org_api_keys.key_hash); shown once at creation, never re-displayed or logged.",
)
_set(
    "IAM-16.1",
    "Yes",
    "CSP-owned",
    "The entire v3 authority-layer governance pipeline IS this control for governed actions: "
    "AuthorityContext.permits() + Policy evaluation + ExecutionAuthorization binding before any dispatch.",
)

# ── Interoperability & Portability ─────────────────────────────────────
_set(
    "IPY-01.1",
    "No",
    "CSP-owned",
    "No formally separate interoperability policy document -- MCP protocol conformance (SPEC.md) is the de facto standard followed.",
)
_set(
    "IPY-01.2",
    "No",
    "CSP-owned",
    "No separate formal policy document; REST/MCP API conventions are documented in code and SPEC.md.",
)
_set(
    "IPY-01.3",
    "No",
    "CSP-owned",
    "No separate formal policy document beyond CONTRIBUTING.md's development conventions.",
)
_set(
    "IPY-01.4",
    "No",
    "CSP-owned",
    "No separate formal policy document; data-exchange format is JSON over documented REST/MCP endpoints.",
)
_set(
    "IPY-01.5",
    "NA",
    "CSP-owned",
    "Not applicable -- no such formal policy documents exist yet to review.",
)
_set(
    "IPY-02.1",
    "Yes",
    "CSP-owned",
    "REST API (GET /api/audit/export, GET /api/governance/evidence, etc.) allows programmatic retrieval of an org's own data.",
)
_set(
    "IPY-03.1",
    "Yes",
    "CSP-owned",
    "HTTPS/TLS (via hosting provider) for all API traffic; MCP's own JSON-RPC-based protocol for tool-call data exchange.",
)
_set(
    "IPY-04.1",
    "No",
    "CSP-owned",
    "No live paying-customer contracts exist yet to specify this in; compliance/DPA_TEMPLATE.md would need this clause added before real use.",
)

# ── Infrastructure & Virtualization Security ──────────────────────────
_set(
    "IVS-01.1",
    "Yes",
    "Shared CSP and 3rd-party",
    "THREAT_MODEL.md covers infrastructure-level threats; underlying virtualization/hypervisor security is fully inherited from Render/Supabase/Upstash (WhitePact runs no VMs/hypervisors directly).",
)
_set("IVS-01.2", "No", "CSP-owned", NO_FORMAL_ANNUAL_REVIEW)
_set(
    "IVS-02.1",
    "Yes",
    "3rd-party outsourced",
    "Resource scaling/capacity is managed by Render (compute)/Supabase (DB)/Upstash (cache)'s own platform tooling, not self-operated capacity planning.",
)
_set(
    "IVS-03.1",
    "No",
    "3rd-party outsourced",
    "Inter-service network monitoring is inherited from the hosting providers' own infrastructure -- not independently monitored by WhitePact.",
)
_set(
    "IVS-03.2",
    "Yes",
    "Shared CSP and 3rd-party",
    "TLS for all inter-service traffic (dashboard <-> DB via Supabase's pooler, dashboard <-> Redis via Upstash) per each provider's own default configuration.",
)
_set(
    "IVS-03.3",
    "Yes",
    "CSP-owned",
    "Bearer-auth on every API endpoint; DB/cache connections use provider-issued credentials, not open access.",
)
_set("IVS-03.4", "No", "CSP-owned", NO_FORMAL_ANNUAL_REVIEW)
_set(
    "IVS-03.5",
    "No",
    "CSP-owned",
    "No formally documented justification-per-open-port/protocol document -- network configuration is managed via each provider's dashboard/environment variables.",
)
_set(
    "IVS-04.1",
    "No",
    "3rd-party outsourced",
    "Host/hypervisor/OS hardening is fully delegated to Render/Supabase/Upstash's managed-platform responsibility -- WhitePact has no direct OS/hypervisor access.",
)
_set(
    "IVS-05.1",
    "Yes",
    "CSP-owned",
    "Production uses the live hosted instance; local/CI test runs use isolated in-memory SQLite (create_engine(':memory:')), never touching production data.",
)
_set(
    "IVS-06.1",
    "Yes",
    "CSP-owned",
    "Org-scoped queries throughout (org_id filtering on every repository method); RBAC enforces per-org, per-role access boundaries. See test_tenant_isolation.py.",
)
_set(
    "IVS-07.1",
    "Yes",
    "Shared CSP and 3rd-party",
    "TLS/HTTPS for all data-in-transit including deployment/CI artifact transfer (GitHub Actions -> PyPI via OIDC, no long-lived credentials transmitted).",
)
_set(
    "IVS-08.1",
    "No",
    "CSP-owned",
    "No formally documented high-risk-environment inventory exists yet -- informal awareness (e.g. the hosted MCP server accepting external tool calls) via THREAT_MODEL.md.",
)
_set(
    "IVS-09.1",
    "Yes",
    "CSP-owned",
    "Defense-in-depth is the explicit design of the v3 authority-layer pipeline: risk classification, "
    "authority constraints, policy engine, content scanning, quarantine, and execution-binding are "
    "independent, layered checks -- see governance/gateway.py's module docstring.",
)

# ── Logging and Monitoring ────────────────────────────────────────────
_set(
    "LOG-01.1",
    "Yes",
    "CSP-owned",
    "ENTERPRISE_SECURITY.md's Audit Trail section + THREAT_MODEL.md document the logging/monitoring approach.",
)
_set("LOG-01.2", "No", "CSP-owned", NO_FORMAL_ANNUAL_REVIEW)
_set(
    "LOG-02.1",
    "Yes",
    "CSP-owned",
    "audit_log and governance_evidence are hash-chained (SHA-256, tamper-evident); GET /api/audit/verify and EvidenceRepository.verify_chain() recompute and detect tampering.",
)
_set(
    "LOG-03.1",
    "Yes",
    "CSP-owned",
    "whitepact_decisions_total, rai_guardrail_scans_total, rai_drift_alerts_total and related Prometheus metrics (dashboard/prometheus.py); structured JSON logging throughout.",
)
_set(
    "LOG-03.2",
    "Yes",
    "CSP-owned",
    "Webhook events (WebhookEvent.DRIFT_ALERT, .GUARDRAIL_TRIGGERED, .APPROVAL_REQUESTED, .BUDGET_EXCEEDED) fire to any org-registered webhook endpoint.",
)
_set(
    "LOG-04.1",
    "Yes",
    "CSP-owned",
    "Audit-log/evidence read endpoints are role-gated (ANALYST+); write access is exclusively through the append-only EvidenceRepository.record()/AuditRepository.write() API, no direct table access exposed.",
)
_set(
    "LOG-05.1",
    "Yes",
    "CSP-owned",
    "QUARANTINE detection (governance/quarantine.py) monitors cross-request DENY-decision patterns per identity and escalates automatically.",
)
_set(
    "LOG-05.2",
    "Yes",
    "CSP-owned",
    "A QUARANTINE decision blocks further action automatically and is itself a hash-chained evidence entry; human review happens via the dashboard's Incidents page.",
)
_set(
    "LOG-06.1",
    "Yes",
    "3rd-party outsourced",
    "System clock/NTP synchronization is inherited from the hosting providers' own infrastructure -- not self-managed.",
)
_set(
    "LOG-07.1",
    "Yes",
    "CSP-owned",
    "governance/evidence.py's EvidenceRecord and db/audit_repository.py define exactly what's logged per event; documented in their own module docstrings.",
)
_set("LOG-07.2", "No", "CSP-owned", NO_FORMAL_ANNUAL_REVIEW)
_set(
    "LOG-08.1",
    "Yes",
    "CSP-owned",
    "EvidenceRecord captures action_id, agent_id, identity_id, decision, reason_codes, risk_tier, policy_version, delegation_chain, timestamps -- real security-relevant fields, not a generic log line.",
)
_set(
    "LOG-09.1",
    "Yes",
    "CSP-owned",
    "Write-once by design (no update/delete method on EvidenceRepository/AuditRepository); hash-chain makes any tampering detectable via verify_chain()/GET /api/audit/verify.",
)
_set(
    "LOG-10.1",
    "No",
    "CSP-owned",
    "No dedicated cryptographic-operations monitoring dashboard exists yet -- key rotation events are manually documented per compliance/KEY_MANAGEMENT.md's procedure.",
)
_set(
    "LOG-11.1",
    "No",
    "CSP-owned",
    "Key lifecycle events (rotation) are manually documented, not automatically logged/monitored.",
)
_set(
    "LOG-12.1",
    "NA",
    "3rd-party outsourced",
    "Not applicable -- WhitePact has no physical facility of its own; physical access logging is the hosting providers' responsibility.",
)
_set(
    "LOG-13.1",
    "Yes",
    "CSP-owned",
    "CI failure notifications (GitHub Actions) + webhook-based alerting for governance anomalies (drift, quarantine, budget) serve this function; no unified 'monitoring system health' dashboard yet.",
)
_set(
    "LOG-13.2",
    "No",
    "CSP-owned",
    "No automated immediate-notification SLA for monitoring-system-itself anomalies -- solo founder checks CI/dashboard state manually.",
)

# ── Security Incident Management, E-Discovery, & Cloud Forensics ─────
_set("SEF-01.1", "Yes", "CSP-owned", "compliance/INCIDENT_RESPONSE_RUNBOOK.md.")
_set("SEF-01.2", "No", "CSP-owned", NO_FORMAL_ANNUAL_REVIEW)
_set(
    "SEF-02.1",
    "Yes",
    "CSP-owned",
    "compliance/INCIDENT_RESPONSE_RUNBOOK.md defines the response process and timelines.",
)
_set("SEF-02.2", "No", "CSP-owned", NO_FORMAL_ANNUAL_REVIEW)
_set(
    "SEF-03.1",
    "Yes",
    "CSP-owned",
    "compliance/INCIDENT_RESPONSE_RUNBOOK.md; no external CSCs to include yet since no paying-customer base exists.",
)
_set(
    "SEF-04.1",
    "No",
    "CSP-owned",
    "Tested once via a tabletop exercise (compliance/TABLETOP_EXERCISE_2026-07-21.md) -- not yet a recurring, scheduled practice.",
)
_set(
    "SEF-05.1",
    "No",
    "CSP-owned",
    "No formal incident metrics program exists yet -- incident count/severity would be tracked manually if/when one occurs.",
)
_set(
    "SEF-06.1",
    "Yes",
    "CSP-owned",
    "The QUARANTINE mechanism (governance/quarantine.py) is exactly this: automated triage of a security-relevant event pattern (repeated denials) with an automatic response.",
)
_set(
    "SEF-07.1",
    "Yes",
    "CSP-owned",
    "compliance/INCIDENT_RESPONSE_RUNBOOK.md's breach-notification section documents the target timeline.",
)
_set(
    "SEF-07.2",
    "No",
    "CSP-owned",
    "No real breach has occurred to test this against; the process is documented but unexercised in practice.",
)
_set(
    "SEF-08.1",
    "No",
    "CSP-owned",
    "No formal points-of-contact list with regulatory/law-enforcement bodies exists yet -- would be established with legal counsel before it's operationally needed.",
)

# ── Supply Chain Management, Transparency, and Accountability ────────
_set(
    "STA-01.1",
    "Yes",
    "CSP-owned",
    "THREAT_MODEL.md explicitly documents the shared-responsibility boundary between WhitePact and its own upstream infra vendors and its own downstream MCP-tool callers.",
)
_set("STA-01.2", "No", "CSP-owned", NO_FORMAL_ANNUAL_REVIEW)
_set(
    "STA-02.1",
    "Yes",
    "CSP-owned",
    "compliance/VENDOR_RISK_ASSESSMENT.md documents each upstream vendor's (Render/Supabase/Upstash) role and inherited responsibilities.",
)
_set(
    "STA-03.1",
    "No",
    "CSC-owned",
    "No formal SSRM-guidance document is published to CSCs yet -- no live paying-customer base to publish it to.",
)
_set(
    "STA-04.1",
    "No",
    "CSP-owned",
    "No formal per-CCM-control SSRM delineation table exists beyond this CAIQ submission itself.",
)
_set(
    "STA-05.1",
    "Yes",
    "CSP-owned",
    "compliance/VENDOR_RISK_ASSESSMENT.md reviews each vendor's own published certifications/documentation.",
)
_set(
    "STA-06.1",
    "Yes",
    "CSP-owned",
    "The portions WhitePact is responsible for (application-layer security, the entire governance pipeline, encryption of specific PII fields) are implemented and tested (1723+ tests); not yet independently audited.",
)
_set(
    "STA-07.1",
    "Yes",
    "CSP-owned",
    "pyproject.toml + SBOM (CycloneDX, generated on every release) is a real, current supply-chain inventory of every dependency.",
)
_set(
    "STA-08.1",
    "No",
    "CSP-owned",
    "No formal periodic review cadence for vendor risk exists yet -- compliance/VENDOR_RISK_ASSESSMENT.md was a point-in-time review.",
)
_set(
    "STA-09.1",
    "No",
    "CSP-owned",
    "No live paying-customer service agreements exist yet -- compliance/DPA_TEMPLATE.md and TERMS_OF_SERVICE.md are drafted but not yet attorney-reviewed or executed.",
)
_set(
    "STA-10.1",
    "NA",
    "CSP-owned",
    "Not applicable -- no such agreements exist yet to review annually.",
)
_set(
    "STA-11.1",
    "No",
    "CSP-owned",
    "No formal annual internal-assessment process exists yet beyond the ad hoc security reviews already documented.",
)
_set(
    "STA-12.1",
    "No",
    "CSP-owned",
    "No formal supply-chain-vendor compliance-requirement policy document exists yet -- dependency vetting today is via pip-audit/dependency-review.yml automated scanning, not contractual vendor requirements.",
)
_set(
    "STA-13.1",
    "No",
    "CSP-owned",
    "No formal periodic supply-chain-partner IT-governance review exists yet.",
)
_set(
    "STA-14.1",
    "No",
    "CSP-owned",
    "No formal periodic security-assessment process for supply-chain organizations exists yet beyond the one-time compliance/VENDOR_RISK_ASSESSMENT.md review.",
)

# ── Threat & Vulnerability Management ─────────────────────────────────
_set(
    "TVM-01.1",
    "Yes",
    "CSP-owned",
    "THREAT_MODEL.md (STRIDE-based) + .github/workflows/security-scan.yml (Bandit + pip-audit, weekly) + dependency-review.yml (every PR).",
)
_set("TVM-01.2", "No", "CSP-owned", NO_FORMAL_ANNUAL_REVIEW)
_set(
    "TVM-02.1",
    "No",
    "CSP-owned",
    "No dedicated endpoint anti-malware policy exists -- no managed endpoint fleet; solo founder's own device is out of this control's real scope.",
)
_set("TVM-02.2", "NA", "CSP-owned", "Not applicable -- no such policy exists yet.")
_set(
    "TVM-03.1",
    "Yes",
    "CSP-owned",
    "pip-audit (weekly + every PR via dependency-review.yml) + Bandit (weekly) with a real, dated example: the nltk PYSEC-2026-597 fix in CHANGELOG.md.",
)
_set(
    "TVM-04.1",
    "Yes",
    "CSP-owned",
    "GitHub Actions runners and pip-audit/Bandit tool versions are refreshed automatically on every scheduled run (they pull the latest vulnerability feed each time).",
)
_set(
    "TVM-05.1",
    "Yes",
    "CSP-owned",
    "pip-audit specifically audits third-party dependencies (not just first-party code) on every PR and weekly schedule.",
)
_set(
    "TVM-06.1",
    "No",
    "3rd-party outsourced",
    "No independent third-party penetration test has been performed yet -- funding-gated. "
    "See compliance/NO_BUDGET_TRUST_PATH.md for the honest interim self-conducted-scan alternative "
    "and the exact language for describing this status to a buyer without overclaiming.",
)
_set(
    "TVM-07.1",
    "Yes",
    "CSP-owned",
    "Bandit (SAST) + pip-audit (dependency CVEs), both scheduled weekly via .github/workflows/security-scan.yml, with today's actual result documented in compliance/NO_BUDGET_TRUST_PATH.md.",
)
_set(
    "TVM-08.1",
    "Yes",
    "CSP-owned",
    "Findings are triaged by real severity (Bandit's HIGH/MEDIUM/LOW, pip-audit's CVE severity) rather than fixed blindly by volume -- see today's documented B104 finding, reviewed and accepted, not blindly 'fixed'.",
)
_set(
    "TVM-09.1",
    "No",
    "CSP-owned",
    "No formal tracked-ticket workflow for vulnerability remediation exists yet -- handled directly via git commits/PRs, with CHANGELOG.md as the record.",
)
_set(
    "TVM-10.1",
    "No",
    "CSP-owned",
    "No formal recurring metrics report exists yet -- security-scan.yml's artifact history is the current, checkable record.",
)

# ── Universal Endpoint Management ─────────────────────────────────────
# No managed device fleet -- solo founder, no UEM/MDM program.
_UEM_NA = "No managed endpoint fleet exists -- solo-founder company, no organization-issued devices to manage under a UEM/MDM program."
_set("UEM-01.1", "No", "CSP-owned", _UEM_NA)
_set("UEM-01.2", "NA", "CSP-owned", "Not applicable -- no such policy exists yet.")
_set("UEM-02.1", "No", "CSP-owned", _UEM_NA)
_set("UEM-03.1", "NA", "CSP-owned", "Not applicable -- no managed endpoint fleet.")
_set("UEM-04.1", "No", "CSP-owned", _UEM_NA)
_set("UEM-05.1", "No", "CSP-owned", _UEM_NA)
_set(
    "UEM-06.1",
    "No",
    "CSP-owned",
    "No formal enforced-lock-screen policy exists -- personal device practice, not organizationally enforced/verified.",
)
_set(
    "UEM-07.1",
    "NA",
    "CSP-owned",
    "Not applicable -- no managed endpoint fleet; application-level change management (git/CI) is unrelated to this control.",
)
_set(
    "UEM-08.1",
    "No",
    "CSP-owned",
    "No organization-mandated full-disk-encryption verification process exists -- personal device practice, not centrally enforced/audited.",
)
_set("UEM-09.1", "No", "CSP-owned", _UEM_NA)
_set("UEM-10.1", "No", "CSP-owned", _UEM_NA)
_set("UEM-11.1", "NA", "CSP-owned", "Not applicable -- no managed endpoint fleet, no DLP program.")
_set("UEM-12.1", "NA", "CSP-owned", "Not applicable -- no managed mobile endpoint fleet.")
_set("UEM-13.1", "NA", "CSP-owned", "Not applicable -- no managed endpoint fleet.")
_set(
    "UEM-14.1",
    "No",
    "3rd-party outsourced",
    "Third-party endpoint security is inherited from each SaaS vendor's (GitHub, PyPI, hosting providers) own security posture -- not independently verified/contracted by WhitePact.",
)
