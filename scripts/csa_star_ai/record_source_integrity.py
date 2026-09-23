# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Record SHA-256 and sheet metadata for pristine CSA upstream workbook."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SOURCE = _REPO / "compliance" / "csa-star-ai" / "source"
_UPSTREAM = _SOURCE / "CSA_AI-CAIQ_v1.1_Official_upstream.xlsx"
_META = _SOURCE / "SOURCE_INTEGRITY.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    if not _UPSTREAM.is_file():
        print(f"Missing upstream workbook: {_UPSTREAM}", file=sys.stderr)
        raise SystemExit(2)
    import openpyxl

    wb = openpyxl.load_workbook(_UPSTREAM, read_only=True, data_only=True)
    meta = json.loads(_META.read_text(encoding="utf-8"))
    meta["acquisition_status"] = "ACQUIRED"
    meta["workbook_filename"] = _UPSTREAM.name
    meta["workbook_sha256"] = _sha256(_UPSTREAM)
    meta["workbook_size_bytes"] = _UPSTREAM.stat().st_size
    meta["sheet_names"] = list(wb.sheetnames)
    meta["retrieval_date"] = datetime.now(UTC).date().isoformat()
    _META.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
