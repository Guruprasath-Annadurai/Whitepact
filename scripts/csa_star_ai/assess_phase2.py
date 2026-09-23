# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Phase 2: role normalization, scope NA, remediation class, full re-audit."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.caiq_answers import ANSWERS
from scripts.csa_star_ai.ai_caiq_supplement import SUPPLEMENT
from scripts.csa_star_ai.evidence_assessor import assess_row, second_pass_challenge
from scripts.csa_star_ai.ledger import ControlAnswer, RemediationLedger
from scripts.csa_star_ai.remediation_classify import apply_remediation_class
from scripts.csa_star_ai.role_scope import apply_role_to_row

_LEDGER = _REPO / "compliance" / "csa-star-ai" / "ledger" / "remediation_ledger.json"
_PHASE1 = _REPO / "compliance" / "csa-star-ai" / "ledger" / "PHASE_1_AUTHORITATIVE_BASELINE.json"
_CHANGES = _REPO / "compliance" / "csa-star-ai" / "ledger" / "phase2_control_changes.csv"
_BACKLOG = _REPO / "compliance" / "csa-star-ai" / "ledger" / "NO_REMEDIATION_BACKLOG.csv"


def _strict_na(row) -> bool:
    if not row.na_candidate or not row.na_rationale:
        return False
    if row.role_applicability in {
        "NOT_APPLICABLE_PHYSICAL_SSRM",
        "NOT_APPLICABLE_MP_SCOPE",
    }:
        return True
    return False


def _apply_scope_response(row, phase1_resp: str) -> None:
    if _strict_na(row):
        row.response = ControlAnswer.NA
        row.justification = row.na_rationale
        row.evidence_type = "ARCHITECTURAL_SSRM"
        row.evidence_strength = row.evidence_strength  # may be updated by assess
        from scripts.csa_star_ai.ledger import EvidenceStrength

        if row.evidence_strength == EvidenceStrength.NONE:
            row.evidence_strength = EvidenceStrength.MODERATE
        row.applicability = "NOT_APPLICABLE"
        row.implementation_state = "OUT_OF_SCOPE"
    elif phase1_resp == "NA" and row.role_applicability == "APPLICABLE_VENDOR_ASSURANCE":
        row.response = ControlAnswer.NO
        row.justification = (
            "Phase 2: NA reversed — WhitePact retains vendor-assurance responsibility "
            "without operating physical/datacenter controls. Provider evidence pending."
        )
        row.applicability = "APPLICABLE"
        row.implementation_state = "PROVIDER_DEPENDENT"


def _write_backlog(ledger: RemediationLedger) -> None:
    fields = [
        "question_id",
        "domain",
        "response",
        "phase2_remediation_class",
        "implementation_state",
        "why_no",
        "missing_evidence",
        "remediation_owner",
        "technical_vs_human",
        "cursor_can_remediate",
        "production_evidence_required",
        "external_party_required",
    ]
    with _BACKLOG.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in ledger.rows:
            if row.response != ControlAnswer.NO:
                continue
            w.writerow(
                {
                    "question_id": row.question_id,
                    "domain": row.domain,
                    "response": row.response.value,
                    "phase2_remediation_class": row.phase2_remediation_class,
                    "implementation_state": row.implementation_state,
                    "why_no": row.justification[:500],
                    "missing_evidence": row.remediation_requirement or row.new_evidence,
                    "remediation_owner": row.implementation_owner,
                    "technical_vs_human": (
                        "provider"
                        if "G_CLOUD" in row.phase2_remediation_class
                        else (
                            "human"
                            if "F_ORGANIZATIONAL" in row.phase2_remediation_class
                            else "technical"
                        )
                    ),
                    "cursor_can_remediate": str(
                        row.phase2_remediation_class
                        in {"A_SOURCE_CODE", "B_RUNTIME_ARCHITECTURE", "E_CI_SUPPLY_CHAIN"}
                    ),
                    "production_evidence_required": str(
                        row.phase2_remediation_class == "D_PRODUCTION_EVIDENCE"
                        or "production" in row.justification.casefold()
                    ),
                    "external_party_required": str(
                        "G_CLOUD" in row.phase2_remediation_class
                        or "I_LEGAL" in row.phase2_remediation_class
                    ),
                }
            )


def main() -> None:
    phase1 = RemediationLedger.model_validate_json(_PHASE1.read_text(encoding="utf-8"))
    p1_map = {r.question_id: r.response.value for r in phase1.rows}

    ledger = RemediationLedger.model_validate_json(_LEDGER.read_text(encoding="utf-8"))
    for i, row in enumerate(ledger.rows):
        row.response = ControlAnswer.UNASSESSED
        row.phase1_response = p1_map.get(row.question_id, "")
        row.before_response = row.phase1_response
        ledger.rows[i] = row

    for i, row in enumerate(ledger.rows):
        p1_resp = row.phase1_response
        before = row.before_response or p1_resp
        hint = ANSWERS.get(row.question_id) or SUPPLEMENT.get(row.question_id)
        assessed = assess_row(row, hint)
        assessed.phase1_response = p1_resp
        assessed.before_response = before
        assessed.domain = row.domain
        assessed.control_title = row.control_title
        assessed.control_specification = row.control_specification
        row = apply_role_to_row(assessed)
        _apply_scope_response(row, p1_resp)
        row = second_pass_challenge(row)
        row = apply_remediation_class(row)
        if row.response.value != row.phase1_response:
            row.changed_in_campaign = True
            row.change_reason = (
                f"Phase2: {row.before_response} -> {row.response.value}; "
                f"{row.role_reasoning[:120]}"
            )
        ledger.rows[i] = row

    # Adversarial YES / NA recheck
    for i, row in enumerate(ledger.rows):
        if row.question_id.startswith("MDS") and _strict_na(row) and row.response != ControlAnswer.NA:
            row.response = ControlAnswer.NA
            row.justification = row.na_rationale
            row.changed_in_campaign = True
            row.change_reason = "Phase2: MDS scope → NA (OSP not MP)"
        if row.response != ControlAnswer.YES:
            ledger.rows[i] = row
            continue
        q = row.question.casefold()
        if "threat_model.md" in " ".join(row.evidence_references).casefold() and not any(
            r.startswith("tests/") for r in row.evidence_references
        ):
            if "annual" in q:
                row.response = ControlAnswer.NO
                row.change_reason = "Phase2: doc-only annual threat model review"
        ledger.rows[i] = row

    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_REPO, text=True).strip()
    ledger.feature_sha = sha
    ledger.phase = "phase2"
    _LEDGER.write_text(ledger.model_dump_json(indent=2), encoding="utf-8")

    lines = [
        "question_id,phase1_response,after_response,change_reason,evidence_strength,"
        "phase2_remediation_class,primary_role,na_rationale"
    ]
    for row in ledger.rows:
        lines.append(
            f"{row.question_id},{row.phase1_response},{row.response.value},"
            f"\"{(row.change_reason or '').replace(chr(34), chr(39))}\","
            f"{row.evidence_strength.value},{row.phase2_remediation_class},"
            f"{row.primary_role},\"{(row.na_rationale or '')[:200].replace(chr(34), chr(39))}\""
        )
    _CHANGES.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _write_backlog(ledger)

    from scripts.csa_star_ai.ingest_workbook import write_matrix

    write_matrix(ledger)

    yes, denom, pct = ledger.applicable_readiness()
    uncl = sum(1 for r in ledger.rows if r.phase2_remediation_class == "UNCLASSIFIED")
    print(
        json.dumps(
            {
                "phase1": phase1.summary(),
                "phase2": ledger.summary(),
                "readiness_pct": round(pct, 2),
                "unclassified_remaining": uncl,
                "evidence_yes": ledger.evidence_quality_counts(),
            },
            indent=2,
        )
    )
    if uncl:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
