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
_DRAFT = _SOURCE / "WhitePact_AI_CAIQ_v1.1_STAR_Level1_COMPLETED_DRAFT.xlsx"
_LEDGER = _REPO / "compliance" / "csa-star-ai" / "ledger" / "remediation_ledger.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not _DRAFT.is_file():
        print("Draft workbook required for sheet preservation.", file=sys.stderr)
        raise SystemExit(2)
    if not _LEDGER.is_file():
        print("Run ingest_workbook.py first.", file=sys.stderr)
        raise SystemExit(2)
    ledger = json.loads(_LEDGER.read_text(encoding="utf-8"))
    by_id = {r["control_id"]: r for r in ledger.get("rows", [])}

    import openpyxl

    shutil.copy2(_DRAFT, args.output)
    wb = openpyxl.load_workbook(args.output)
    ws = wb[wb.sheetnames[-1]]
    for row in ws.iter_rows(min_row=1):
        cid = str(row[0].value or "").strip()
        if cid not in by_id:
            continue
        entry = by_id[cid]
        final = entry.get("final_answer") or entry.get("current_answer")
        if len(row) > 2:
            row[2].value = final
        if len(row) > 3:
            row[3].value = entry.get("ssrm_owner") or row[3].value
        if len(row) > 4:
            row[4].value = entry.get("final_evidence") or entry.get("current_evidence") or row[4].value
        if len(row) > 5:
            row[5].value = entry.get("customer_responsibility") or row[5].value
    wb.save(args.output)
    print(f"Wrote {args.output} ({len(by_id)} ledger entries applied)")


if __name__ == "__main__":
    main()
