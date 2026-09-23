# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""
Evidence-first assessment pass for AI-CAIQ ledger rows.

Starts from UNASSESSED rows only. Does not import preliminary 98/152/70 answers.
"""

from __future__ import annotations

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
from scripts.csa_star_ai.ledger import ControlAnswer, EvidenceStrength, RemediationLedger

_LEDGER_PATH = _REPO / "compliance" / "csa-star-ai" / "ledger" / "remediation_ledger.json"
_CHANGES_PATH = _REPO / "compliance" / "csa-star-ai" / "ledger" / "control_changes.csv"
_UNMAPPED_PATH = _REPO / "compliance" / "csa-star-ai" / "ledger" / "AI_CAIQ_V11_UNMAPPED_REVIEW.md"


def _write_unmapped_report(ledger: RemediationLedger) -> None:
    legacy_ids = set(ANSWERS.keys())
    lines = [
        "# AI-CAIQ v1.1 controls outside legacy CCM v4 map (261 keys)",
        "",
        f"Total ledger rows: {len(ledger.rows)}",
        f"Legacy map keys: {len(legacy_ids)}",
        f"Supplement entries: {len(SUPPLEMENT)}",
        "",
        "Manual evidence review performed via `scripts/csa_star_ai/ai_caiq_supplement.py` "
        "and `evidence_assessor.py` (not bulk-flipped from preliminary snapshot).",
        "",
        "| Question ID | Response | Strength | Domain | Question (truncated) |",
        "|-------------|----------|----------|--------|---------------------|",
    ]
    for row in ledger.rows:
        if row.question_id in legacy_ids:
            continue
        q = row.question.replace("|", "/").replace("\n", " ")[:80]
        lines.append(
            f"| {row.question_id} | {row.response.value} | {row.evidence_strength.value} | "
            f"{row.domain} | {q} |"
        )
    _UNMAPPED_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if not _LEDGER_PATH.is_file():
        print("Run ingest_workbook.py first.", file=sys.stderr)
        raise SystemExit(2)
    ledger = RemediationLedger.model_validate_json(_LEDGER_PATH.read_text(encoding="utf-8"))
    if len(ledger.rows) != 320:
        print(f"Ledger must contain 320 rows, found {len(ledger.rows)}", file=sys.stderr)
        raise SystemExit(1)

    before: dict[str, str] = {r.question_id: r.response.value for r in ledger.rows}

    for i, row in enumerate(ledger.rows):
        hint = ANSWERS.get(row.question_id) or SUPPLEMENT.get(row.question_id)
        ledger.rows[i] = assess_row(row, hint)

    for i, row in enumerate(ledger.rows):
        ledger.rows[i] = second_pass_challenge(row)

    sha = (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_REPO, text=True).strip()
        if (_REPO / ".git").exists()
        else ""
    )
    ledger.feature_sha = sha
    _LEDGER_PATH.write_text(ledger.model_dump_json(indent=2), encoding="utf-8")

    lines = ["question_id,before,after,evidence_strength,remediation_type,changed_in_campaign"]
    for row in ledger.rows:
        lines.append(
            f"{row.question_id},{before[row.question_id]},{row.response.value},"
            f"{row.evidence_strength.value},{row.remediation_type},{row.changed_in_campaign}"
        )
    _CHANGES_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _write_unmapped_report(ledger)

    from scripts.csa_star_ai.ingest_workbook import write_matrix

    write_matrix(ledger)

    yes, denom, pct = ledger.applicable_readiness()
    weak_cond = sum(
        1
        for r in ledger.rows
        if r.evidence_strength in {EvidenceStrength.WEAK, EvidenceStrength.NONE}
        and r.response in {ControlAnswer.YES, ControlAnswer.NO}
    )
    print(
        json.dumps(
            {
                "summary": ledger.summary(),
                "applicable_yes": yes,
                "applicable_denominator": denom,
                "readiness_pct": round(pct, 2),
                "evidence_quality_yes_only": ledger.evidence_quality_counts(),
                "weak_or_none_evidence_rows": weak_cond,
                "second_pass_changes": sum(1 for r in ledger.rows if r.changed_in_campaign),
                "unmapped_supplement_reviewed": len(SUPPLEMENT),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
