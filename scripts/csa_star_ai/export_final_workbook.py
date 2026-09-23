# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Export FINAL AI-CAIQ workbook from remediation ledger (respondent columns only)."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SOURCE = _REPO / "compliance" / "csa-star-ai" / "source"
_UPSTREAM = _SOURCE / "CSA_AI-CAIQ_v1.1_Official_upstream.xlsx"
_LEDGER = _REPO / "compliance" / "csa-star-ai" / "ledger" / "remediation_ledger.json"


def _pick_sheet(wb):
    for name in wb.sheetnames:
        lower = name.lower()
        if "caiq" in lower or "questionnaire" in lower or "ai-caiq" in lower:
            return wb[name]
    return wb[wb.sheetnames[0]]


def _workbook_answer(resp: str) -> str:
    if resp == "YES":
        return "Yes"
    if resp == "NO":
        return "No"
    if resp == "NA":
        return "NA"
    return "No"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not _UPSTREAM.is_file():
        print("Pristine upstream workbook required.", file=sys.stderr)
        raise SystemExit(2)
    if not _LEDGER.is_file():
        print("Run ingest_workbook.py and assess_evidence.py first.", file=sys.stderr)
        raise SystemExit(2)
    ledger = json.loads(_LEDGER.read_text(encoding="utf-8"))
    by_id = {r["question_id"]: r for r in ledger.get("rows", [])}
    unassessed = sum(1 for r in ledger.get("rows", []) if r.get("response") == "UNASSESSED")
    if unassessed:
        print(f"Refusing export: {unassessed} rows still UNASSESSED", file=sys.stderr)
        raise SystemExit(1)

    import openpyxl

    shutil.copy2(_UPSTREAM, args.output)
    wb = openpyxl.load_workbook(args.output)
    ws = _pick_sheet(wb)
    header_row = None
    col_map: dict[str, int] = {}
    for idx, row in enumerate(ws.iter_rows(min_row=1, max_row=20), start=1):
        vals = [str(c.value or "").strip().lower() for c in row]
        if "question id" in vals:
            header_row = idx
            col_map = {v: i for i, v in enumerate(vals)}
            break
    if header_row is None:
        raise SystemExit("Could not find header row")

    def _idx(*names: str) -> int | None:
        for name in names:
            if name in col_map:
                return col_map[name]
            for key, i in col_map.items():
                if name in key:
                    return i
        return None

    qid_idx = _idx("question id") or 0
    ans_idx = _idx(
        "service provider ai-caiq answer",
        "csp caiq answer",
        "caiq answer",
    )
    ssrm_idx = _idx("ssrm control ownership")
    impl_idx = _idx(
        "csp implementation description (optional/recommended)",
        "implementation description",
    )
    cust_idx = _idx(
        "csc responsibilities  (optional/recommended)",
        "csc responsibilities (optional/recommended)",
    )

    for row in ws.iter_rows(min_row=header_row + 1):
        if qid_idx >= len(row):
            continue
        qid = str(row[qid_idx].value or "").strip()
        if qid not in by_id:
            continue
        entry = by_id[qid]
        resp = entry.get("response", "NO")
        if ans_idx is not None and ans_idx < len(row):
            row[ans_idx].value = _workbook_answer(str(resp))
        if ssrm_idx is not None and ssrm_idx < len(row):
            row[ssrm_idx].value = (
                entry.get("ssrm_owner") or entry.get("implementation_owner") or row[ssrm_idx].value
            )
        if impl_idx is not None and impl_idx < len(row):
            row[impl_idx].value = (
                entry.get("implementation_description") or entry.get("justification") or ""
            )
        if cust_idx is not None and cust_idx < len(row):
            row[cust_idx].value = entry.get("customer_responsibility") or row[cust_idx].value
    wb.save(args.output)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
