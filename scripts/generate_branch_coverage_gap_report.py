#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Emit BRANCH_COVERAGE_GAP_REPORT.md from coverage.json (branch detail)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

CRITICALITY = {
    "authority": "P0",
    "grant": "P0",
    "revocation": "P0",
    "tenant": "P0",
    "auth": "P0",
    "session": "P0",
    "policy": "P1",
    "risk": "P1",
    "approval": "P1",
    "execution": "P1",
    "mcp": "P1",
    "audit": "P1",
    "evidence": "P1",
    "billing": "P1",
    "paddle": "P1",
    "oauth": "P1",
    "redaction": "P1",
    "dashboard/app.py": "P1",
    "enterprise/security": "P0",
}


def criticality_for(path: str) -> str:
    low = path.lower()
    for key, level in CRITICALITY.items():
        if key in low:
            return level
    return "P2"


def main() -> int:
    cov_path = Path(sys.argv[1] if len(sys.argv) > 1 else "coverage.json")
    out_path = Path(sys.argv[2] if len(sys.argv) > 2 else "BRANCH_COVERAGE_GAP_REPORT.md")
    if not cov_path.exists():
        print(f"{cov_path} missing", file=sys.stderr)
        return 2

    data = json.loads(cov_path.read_text())
    totals = data["totals"]
    nb = totals.get("num_branches", 0)
    cb = totals.get("covered_branches", 0)
    pct = 100.0 * cb / nb if nb else 0.0

    rows: list[dict] = []
    for path, entry in data.get("files", {}).items():
        if not path.startswith("src/responsibleai"):
            continue
        s = entry.get("summary", {})
        file_nb = s.get("num_branches", 0) or 0
        if not file_nb:
            continue
        file_cb = s.get("covered_branches", 0) or 0
        missing = file_nb - file_cb
        missing_lines = sorted(entry.get("missing_lines", []) or [])
        rows.append(
            {
                "path": path,
                "total": file_nb,
                "covered": file_cb,
                "missing": missing,
                "pct": 100.0 * file_cb / file_nb,
                "missing_lines": missing_lines[:40],
                "criticality": criticality_for(path),
            }
        )
    rows.sort(key=lambda r: r["missing"], reverse=True)

    lines = [
        "# Branch coverage gap report",
        "",
        f"Source: `{cov_path}`",
        "",
        "## Totals",
        "",
        f"- Pure branch coverage: **{pct:.2f}%** ({cb}/{nb})",
        f"- OpenSSF required: **80.00%**",
        f"- Gap: **{max(0.0, 80.0 - pct):.2f}** percentage points",
        f"- Branches to cover (approx): **{max(0, int(0.805 * nb) - cb)}** for 80.5% buffer target",
        "",
        "## Production files (sorted by missing branches)",
        "",
        "| File | Total | Covered | Missing | Branch % | Criticality | Sample missing lines |",
        "|------|------:|--------:|--------:|---------:|:-----------:|----------------------|",
    ]
    for r in rows:
        sample = ", ".join(str(x) for x in r["missing_lines"][:8])
        if len(r["missing_lines"]) > 8:
            sample += ", …"
        lines.append(
            f"| `{r['path']}` | {r['total']} | {r['covered']} | {r['missing']} | "
            f"{r['pct']:.1f}% | {r['criticality']} | {sample or '—'} |"
        )
    lines.extend(
        [
            "",
            "## Recommended test areas (priority order)",
            "",
            "1. Authority / grant / revocation / fail-closed paths",
            "2. Tenant isolation and session/auth boundaries",
            "3. Policy / risk / approvals",
            "4. MCP malformed upstream and execution errors",
            "5. Audit / evidence integrity",
            "6. Billing failure paths (no entitlement grant)",
            "7. Enterprise security service deny paths",
            "8. Dashboard API error handling (batch after security core)",
            "",
        ]
    )
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path} ({len(rows)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
