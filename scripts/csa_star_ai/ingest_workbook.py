# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Ingest AI-CAIQ v1.1 draft workbook into remediation_ledger.json."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.csa_star_ai.ledger import ControlAnswer, RemediationLedger, RemediationLedgerRow
_SOURCE = _REPO / "compliance" / "csa-star-ai" / "source"
_DRAFT_NAME = "WhitePact_AI_CAIQ_v1.1_STAR_Level1_COMPLETED_DRAFT.xlsx"
_LEDGER_PATH = _REPO / "compliance" / "csa-star-ai" / "ledger" / "remediation_ledger.json"
_MATRIX_PATH = _REPO / "compliance" / "csa-star-ai" / "CONTROL_MATRIX.md"

_CONTROL_ID_RE = re.compile(r"^[A-Z][A-Za-z0-9&-]+\-\d+\.\d+$")


def _normalize_answer(raw: str | None) -> ControlAnswer:
    if raw is None:
        return ControlAnswer.NO
    folded = str(raw).strip().upper()
    if folded in {"YES", "Y"}:
        return ControlAnswer.YES
    if folded in {"NA", "N/A", "NOT APPLICABLE"}:
        return ControlAnswer.NA
    return ControlAnswer.NO


def _find_questionnaire_sheet(workbook) -> object:
    for name in workbook.sheetnames:
        if "caiq" in name.lower() or "questionnaire" in name.lower() or "ai" in name.lower():
            return workbook[name]
    return workbook[workbook.sheetnames[-1]]


def ingest(path: Path) -> RemediationLedger:
    try:
        import openpyxl
    except ImportError:
        raise SystemExit("openpyxl required: pip install openpyxl") from None

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = _find_questionnaire_sheet(wb)
    rows: list[RemediationLedgerRow] = []
    for cells in ws.iter_rows(values_only=True):
        if not cells or len(cells) < 3:
            continue
        control_id = str(cells[0] or "").strip()
        if not _CONTROL_ID_RE.match(control_id):
            continue
        question = str(cells[1] or "").strip()
        answer = _normalize_answer(str(cells[2] if len(cells) > 2 else ""))
        ssrm = str(cells[3] or "").strip() if len(cells) > 3 else ""
        evidence = str(cells[4] or "").strip() if len(cells) > 4 else ""
        customer = str(cells[5] or "").strip() if len(cells) > 5 else ""
        domain = control_id.split("-", 1)[0] if "-" in control_id else ""
        rows.append(
            RemediationLedgerRow(
                control_id=control_id,
                domain=domain,
                question=question,
                current_answer=answer,
                ssrm_owner=ssrm,
                current_evidence=evidence,
                customer_responsibility=customer,
                final_answer=answer,
                status="baseline",
            )
        )
    if len(rows) < 300:
        print(
            f"WARNING: only {len(rows)} control rows parsed; expected ~320. "
            "Check workbook column layout (A=ID, B=question, C=answer).",
            file=sys.stderr,
        )
    return RemediationLedger(rows=rows)


def write_matrix(ledger: RemediationLedger) -> None:
    lines = [
        "# AI-CAIQ Control Matrix (generated)",
        "",
        f"Rows: {len(ledger.rows)}",
        "",
        "| Control ID | Answer | SSRM | Evidence (truncated) |",
        "|------------|--------|------|----------------------|",
    ]
    for row in ledger.rows[:50]:
        ev = (row.current_evidence or "")[:80].replace("|", "/")
        lines.append(
            f"| {row.control_id} | {row.current_answer.value} | {row.ssrm_owner} | {ev} |"
        )
    if len(ledger.rows) > 50:
        lines.append(f"| … | ({len(ledger.rows) - 50} more rows) | | See remediation_ledger.json |")
    _MATRIX_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    draft = _SOURCE / _DRAFT_NAME
    if not draft.is_file():
        print(f"Missing draft workbook: {draft}", file=sys.stderr)
        print("Copy audit file per compliance/csa-star-ai/source/README.md (OA-001).", file=sys.stderr)
        raise SystemExit(2)
    ledger = ingest(draft)
    _LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    _LEDGER_PATH.write_text(ledger.model_dump_json(indent=2), encoding="utf-8")
    write_matrix(ledger)
    snap = json.loads(
        (_REPO / "compliance/csa-star-ai/ledger/BASELINE_AUDIT_SNAPSHOT.json").read_text()
    )
    snap["workbook_ingested"] = True
    snap["ingested_row_count"] = len(ledger.rows)
    snap["ingested_totals"] = ledger.summary()
    (_REPO / "compliance/csa-star-ai/ledger/BASELINE_AUDIT_SNAPSHOT.json").write_text(
        json.dumps(snap, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Ingested {len(ledger.rows)} controls → {_LEDGER_PATH}")


if __name__ == "__main__":
    main()
