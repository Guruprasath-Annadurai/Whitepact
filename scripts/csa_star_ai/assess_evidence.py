# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""
Evidence-first assessment pass for AI-CAIQ ledger rows.

Starts from UNASSESSED rows only. Does not import preliminary 98/152/70 answers.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.caiq_answers import ANSWERS
from scripts.csa_star_ai.ledger import (
    ControlAnswer,
    EvidenceStrength,
    RemediationCategory,
    RemediationLedger,
    RemediationLedgerRow,
)

_LEDGER_PATH = _REPO / "compliance" / "csa-star-ai" / "ledger" / "remediation_ledger.json"
_CHANGES_PATH = _REPO / "compliance" / "csa-star-ai" / "ledger" / "control_changes.csv"

_PROVIDER_KEYWORDS = (
    "datacenter",
    "physical security",
    "cctv",
    "guard",
    "fire suppression",
    "rack",
)
_ORG_ONLY_KEYWORDS = (
    "annual review",
    "at least annually",
    "third-party audit",
    "independent audit",
    "background check",
    "employee termination",
    "security awareness training",
)
_NA_PHYSICAL = (
    "physical access to the data center",
    "physical access to data centers",
    "cctv",
    "guards",
    "fire suppression",
)


def _path_exists(rel: str) -> bool:
    return (_REPO / rel).is_file()


def _classify_evidence(desc: str) -> tuple[ControlAnswer, EvidenceStrength, str, list[str]]:
    refs: list[str] = []
    lowered = desc.lower()
    if "source-code verified" in lowered or "source code" in lowered:
        for token in re.findall(r"[\w./-]+\.(?:py|yml|md)", desc):
            if _path_exists(token):
                refs.append(token)
        if refs:
            return ControlAnswer.YES, EvidenceStrength.STRONG, desc, refs
        return ControlAnswer.NO, EvidenceStrength.WEAK, "Cited paths not found in repository.", refs
    if "documented process" in lowered:
        return ControlAnswer.NO, EvidenceStrength.WEAK, "DOCUMENTED PROCESS without operational proof.", refs
    if "organizational control" in lowered or "not implemented" in lowered:
        return ControlAnswer.NO, EvidenceStrength.NONE, desc, refs
    if "deployment verified" in lowered:
        return ControlAnswer.NO, EvidenceStrength.NONE, "DEPLOYMENT evidence required (owner/provider).", refs
    if "owner assertion" in lowered:
        return ControlAnswer.NO, EvidenceStrength.NONE, "OWNER ASSERTION REQUIRED.", refs
    return ControlAnswer.NO, EvidenceStrength.NONE, "Insufficient evidence class in mapping.", refs


def _heuristic_na(question: str) -> str | None:
    q = question.casefold()
    for phrase in _NA_PHYSICAL:
        if phrase in q:
            return "WhitePact does not operate physical datacenters; control allocated to cloud provider SSRM."
    return None


def _heuristic_category(question: str, response: ControlAnswer) -> RemediationCategory:
    q = question.casefold()
    if response == ControlAnswer.NA:
        return RemediationCategory.CLOUD_SUBPROCESSOR
    if any(k in q for k in _PROVIDER_KEYWORDS):
        return RemediationCategory.CLOUD_SUBPROCESSOR
    if any(k in q for k in _ORG_ONLY_KEYWORDS):
        return RemediationCategory.ORGANIZATIONAL
    if "customer" in q or "tenant" in q:
        return RemediationCategory.CUSTOMER_SHARED
    return RemediationCategory.UNCLASSIFIED


def assess_row(row: RemediationLedgerRow) -> RemediationLedgerRow:
    if row.response != ControlAnswer.UNASSESSED:
        return row

    na_reason = _heuristic_na(row.question)
    if na_reason:
        row.response = ControlAnswer.NA
        row.justification = na_reason
        row.evidence_strength = EvidenceStrength.MODERATE
        row.evidence_type = "ARCHITECTURAL_SSRM"
        row.provider_dependency = "Cloud service provider"
        row.remediation_type = RemediationCategory.CLOUD_SUBPROCESSOR
        row.status = "assessed"
        return row

    hint = ANSWERS.get(row.question_id)
    if hint:
        _ans, _own, desc = hint
        response, strength, justification, refs = _classify_evidence(desc)
        row.response = response
        row.evidence_strength = strength
        row.justification = justification
        row.evidence_references = refs
        row.evidence_type = "REPOSITORY_EVIDENCE_REVIEW"
        row.implementation_owner = "CSP (WhitePact)"
        row.ssrm_owner = _own
        row.implementation_description = desc[:2000]
        row.partial_implementation = strength in {EvidenceStrength.WEAK, EvidenceStrength.MODERATE}
        row.remediation_type = _heuristic_category(row.question, row.response)
        row.status = "assessed"
        return row

    # Unknown AI-specific control (not in legacy CCM v4 map)
    row.response = ControlAnswer.NO
    row.evidence_strength = EvidenceStrength.NONE
    row.justification = (
        "No independent evidence mapping for this AI-CAIQ v1.1 control ID yet. "
        "Manual review required before YES/NA."
    )
    row.remediation_type = RemediationCategory.UNCLASSIFIED
    row.status = "assessed"
    return row


def main() -> None:
    if not _LEDGER_PATH.is_file():
        print("Run ingest_workbook.py first.", file=sys.stderr)
        raise SystemExit(2)
    ledger = RemediationLedger.model_validate_json(_LEDGER_PATH.read_text(encoding="utf-8"))
    if len(ledger.rows) != 320:
        print(f"Ledger must contain 320 rows, found {len(ledger.rows)}", file=sys.stderr)
        raise SystemExit(1)

    for i, row in enumerate(ledger.rows):
        updated = assess_row(row)
        ledger.rows[i] = updated

    sha = (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_REPO, text=True).strip()
        if (_REPO / ".git").exists()
        else ""
    )
    ledger.feature_sha = sha
    _LEDGER_PATH.write_text(ledger.model_dump_json(indent=2), encoding="utf-8")

    lines = ["question_id,before,after,evidence_strength,remediation_type"]
    for row in ledger.rows:
        lines.append(
            f"{row.question_id},UNASSESSED,{row.response.value},{row.evidence_strength.value},{row.remediation_type}"
        )
    _CHANGES_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    yes, denom, pct = ledger.applicable_readiness()
    print(json.dumps({"summary": ledger.summary(), "applicable_yes": yes, "applicable_denominator": denom, "readiness_pct": round(pct, 2), "evidence_quality": ledger.evidence_quality_counts()}, indent=2))


if __name__ == "__main__":
    main()
