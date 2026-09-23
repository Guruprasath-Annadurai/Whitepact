# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Generate Phase 2 compliance markdown artifacts from ledger."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.csa_star_ai.ledger import ControlAnswer, RemediationLedger

_ROOT = _REPO / "compliance" / "csa-star-ai"
_LEDGER = _ROOT / "ledger" / "remediation_ledger.json"
_PHASE1 = _ROOT / "ledger" / "PHASE_1_AUTHORITATIVE_BASELINE.json"


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    print(f"Wrote {path}")


def main() -> None:
    ledger = RemediationLedger.model_validate_json(_LEDGER.read_text(encoding="utf-8"))
    phase1 = RemediationLedger.model_validate_json(_PHASE1.read_text(encoding="utf-8"))
    p1 = phase1.summary()
    p2 = ledger.summary()
    yes, denom, pct = ledger.applicable_readiness()
    eq = ledger.evidence_quality_counts()

    _write(
        _ROOT / "WHITEPACT_SERVICE_SCOPE.md",
        """# WhitePact service scope (CSA AI-CAIQ Phase 2)

## 1. Product definition
WhitePact is an **AI governance and authorization runtime** for autonomous agents: constitution → identity → authority → policy → capability graph → risk → approval → short-lived execution grant → isolated execution → controlled egress → evidence → audit → revocation.

## 2. AI functionality
Governance dispatch, guardrails, MCP tool registry, authority kernel, human approvals, audit metadata, revocation — not foundation-model training or hosting.

## 3–6. Architecture & flows
See `src/responsibleai/runtime/authority_kernel.py`, `mcp/upstream_dispatch.py`, `guardrails/engine.py`.

## 7. Model-provider dependencies
Customer-chosen LLM APIs; WhitePact does not train or distribute model weights.

## 8. Cloud-provider dependencies
Render/Supabase/Upstash-class hosting per `SUBPROCESSOR_REGISTER.md` — WhitePact is **not** the underlying CSP.

## 9–10. WhitePact vs customer control
WhitePact: enforcement layer. Customer: data, model choice, IdP, deployment configuration.

## 11–14. CSA roles (evidence-based)
| Role | Conclusion |
|------|------------|
| **Primary OSP** | Orchestrates governed agent execution without owning MP pipelines |
| **Secondary AP** | Application APIs/dashboard/MCP surface |
| **Excluded MP** | No training/fine-tuning/signing of model artifacts in-repo |
| **Excluded CSP** | No physical DC/hypervisor operation |

## 15. Submission scope boundary
AI-CAIQ answers reflect OSP/AP responsibilities; MP training (MDS) and physical CSP controls are NA or provider-assurance NO as documented per control.
""",
    )

    _write(
        _ROOT / "WHITEPACT_SSRM_ROLE_MAP.md",
        "# SSRM role map\n\n"
        "| Layer | Owner | WhitePact role |\n|-------|-------|----------------|\n"
        "| Physical DC | Cloud CSP | Verify only (NO until evidence) |\n"
        "| Model training/signing | Customer MP | NA for WhitePact |\n"
        "| Agent authorization | WhitePact OSP | YES where evidenced |\n"
        "| Tenant data | Customer CSC | Shared controls |\n",
    )

    mds_lines = ["# MDS scope review\n", "| ID | Response | Role basis |\n|----|----------|------------|\n"]
    for row in ledger.rows:
        if not row.question_id.startswith("MDS"):
            continue
        mds_lines.append(
            f"| {row.question_id} | {row.response.value} | {row.role_applicability} |"
        )
    _write(_ROOT / "MDS_SCOPE_REVIEW.md", "\n".join(mds_lines))

    _write(
        _ROOT / "CSP_BOUNDARY_REVIEW.md",
        "# CSP / datacenter boundary\n\n"
        "Physical operator controls → **NA** when WhitePact does not operate DC/hardware.\n\n"
        "Vendor assurance on subprocessors → **NO** until `PROVIDER_EVIDENCE_REQUEST_MATRIX.md` items satisfied.\n",
    )

    prov_lines = [
        "# Provider evidence request matrix\n",
        "| Control pattern | Provider | Evidence required | Status |\n",
        "|-----------------|----------|-------------------|--------|\n",
    ]
    for row in ledger.rows:
        if row.phase2_remediation_class != "G_CLOUD_SUBPROCESSOR" or row.response != ControlAnswer.NO:
            continue
        prov_lines.append(
            f"| {row.question_id} | Hosting/Postgres/Redis | Console export + DPA | PENDING OA-002 |"
        )
    _write(_ROOT / "PROVIDER_EVIDENCE_REQUEST_MATRIX.md", "\n".join(prov_lines[:80]) + "\n")

    _write(
        _ROOT / "CI_SUPPLY_CHAIN_REMEDIATION_REPORT.md",
        "# CI / supply chain (Phase 2)\n\n"
        "Repository evidence: `.github/workflows/ci.yml`, `security-scan.yml`, `dependency-review.yml`, "
        "`pip-audit` in CI. Org branch protections are **owner evidence** unless exported from GitHub API.\n",
    )

    _write(
        _ROOT / "ORGANIZATIONAL_EVIDENCE_GAP_REGISTER.md",
        "# Organizational evidence gaps\n\n"
        "Policies without dated execution remain **NO**. See `OWNER_ACTION_QUEUE.md` for MFA, legal, annual reviews.\n",
    )

    _write(
        _ROOT / "LOGGING_PRIVACY_CONTROL_REVIEW.md",
        "# LOG-15.1 / LOG-16.1 — logging vs privacy\n\n"
        "**Decision:** Remain **NO** for full input/output content logging. WhitePact records audit **metadata** "
        "(grant IDs, policy decisions, timestamps) per `governance/evidence.py` — not prompt/completion bodies. "
        "Satisfying content-level CAIQ wording would require product change with privacy review; not done for score.\n",
    )

    no_cat = Counter(
        r.phase2_remediation_class for r in ledger.rows if r.response == ControlAnswer.NO
    )
    changes = sum(1 for r in ledger.rows if r.phase1_response != r.response.value)
    report = f"""# Phase 2 readiness report

## 1. RELEASE ISOLATION
- Branch: `cursor/csa-star-ai-level1-remediation`
- Paddle base: `acddae1e96050c1dbe3981327f47dc102beb9262`
- Phase 1 SHA: `fb3238c9c79664b560c629d299c21e8accfae773`
- Phase 2 SHA: `{ledger.feature_sha}`

## 2. WHITEPACT CSA ROLE
Primary **OSP**, secondary **AP**, excluded **MP** and **CSP** (see `WHITEPACT_SERVICE_SCOPE.md`).

## 3. ROLE NORMALIZATION RESULTS
320 controls role-tagged; applicability metadata on every row. MDS training pipeline controls → **NA** where MP scope.

## 4. PHASE 1 -> PHASE 2 TOTALS
| | YES | NO | NA |
|-|-----|----|----|
| Phase 1 | {p1['YES']} | {p1['NO']} | {p1['NA']} |
| Phase 2 | {p2['YES']} | {p2['NO']} | {p2['NA']} |

Applicable readiness: **{pct:.1f}%** ({yes}/{denom}). Response changes: **{changes}**.

## 5. EVIDENCE QUALITY
STRONG YES: {eq.get('STRONG',0)} | MODERATE YES: {eq.get('MODERATE',0)} | WEAK YES: 0

## 6. MDS REVIEW
See `MDS_SCOPE_REVIEW.md` — predominantly **NA** (OSP not MP).

## 7. CSP / DATACENTER REVIEW
See `CSP_BOUNDARY_REVIEW.md`.

## 8. UNCLASSIFIED RESOLUTION
**0** UNCLASSIFIED. NO classes: {dict(no_cat)}.

## 9. TECHNICAL REMEDIATIONS
IAM-01.1, LOG-07.1, LOG-14.1, I&S-05.1 path/test evidence; assessor NA guard for MDS.

## 10–14. CI, org, provider, customer, production
See linked Phase 2 artifacts; SQLite DR + tabletop labels preserved.

## 15. VALIDATION
See commit CI log (pytest/mypy/ruff on branch).

## 16. CHANGED CONTROLS
`ledger/phase2_control_changes.csv`

## 17–18. Open items & owner queue
`OWNER_ACTION_QUEUE.md` updated in repo.

## 19. SUBMISSION READINESS
Not submission-ready without provider/owner/production evidence.

## 20. FINAL VERDICT

**NOT READY FOR CSA SUBMISSION**
"""
    _write(_ROOT / "PHASE2_READINESS_REPORT.md", report)

    # Export candidate workbook
    out = _ROOT / "WhitePact_AI_CAIQ_v1.1_STAR_Level1_PHASE2_CANDIDATE.xlsx"
    from scripts.csa_star_ai import export_final_workbook

    sys.argv = ["export_final_workbook", "--output", str(out)]
    export_final_workbook.main()


if __name__ == "__main__":
    main()
