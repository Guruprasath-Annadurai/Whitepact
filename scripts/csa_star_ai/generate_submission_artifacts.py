# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Generate FINAL readiness report, evidence manifest, and workbook export."""

from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.csa_star_ai.ledger import ControlAnswer, EvidenceStrength, RemediationLedger  # noqa: E402

_COMPLIANCE = _REPO / "compliance" / "csa-star-ai"
_LEDGER_PATH = _COMPLIANCE / "ledger" / "remediation_ledger.json"
_INTEGRITY = _COMPLIANCE / "source" / "SOURCE_INTEGRITY.json"
_FINAL_XLSX = _COMPLIANCE / "WhitePact_AI_CAIQ_v1.1_STAR_Level1_FINAL.xlsx"
_READINESS = _COMPLIANCE / "FINAL_READINESS_REPORT.md"
_MANIFEST = _COMPLIANCE / "SUBMISSION_EVIDENCE_MANIFEST.md"


def _verdict(ledger: RemediationLedger, strong_yes: int) -> str:
    summary = ledger.summary()
    if summary.get("UNASSESSED", 0) > 0:
        return "NOT READY FOR CSA SUBMISSION"
    open_provider = sum(
        1
        for r in ledger.rows
        if r.response == ControlAnswer.NO
        and "provider" in (r.provider_dependency or "").casefold()
    )
    if summary.get("NO", 0) > 120 or open_provider > 40:
        return "NOT READY FOR CSA SUBMISSION"
    if summary.get("NO", 0) > 60:
        return "CONDITIONALLY READY — OWNER ACTIONS REMAIN"
    if strong_yes < 30:
        return "CONDITIONALLY READY — OWNER ACTIONS REMAIN"
    return "READY FOR HUMAN CSA SUBMISSION REVIEW"


def _write_readiness(ledger: RemediationLedger, meta: dict, feature_sha: str) -> None:
    yes, denom, pct = ledger.applicable_readiness()
    eq = ledger.evidence_quality_counts()
    summary = ledger.summary()
    verdict = _verdict(ledger, eq.get("STRONG", 0))
    no_by_cat: dict[str, list[str]] = defaultdict(list)
    for row in ledger.rows:
        if row.response == ControlAnswer.NO:
            no_by_cat[str(row.remediation_type)].append(row.question_id)

    lines = [
        "# Final readiness report — CSA STAR for AI Level 1",
        "",
        "**Campaign branch:** `cursor/csa-star-ai-level1-remediation`  ",
        f"**Feature SHA assessed:** `{feature_sha}`  ",
        f"**Upstream workbook SHA-256:** `{meta.get('workbook_sha256', '')}`  ",
        "**Designation:** Preparing self-assessment — not CSA-certified.",
        "",
        "## Authoritative totals",
        "",
        "| YES | NO | NA | UNASSESSED |",
        "|-----|----|----|------------|",
        f"| {summary.get('YES', 0)} | {summary.get('NO', 0)} | {summary.get('NA', 0)} | {summary.get('UNASSESSED', 0)} |",
        "",
        f"**Applicable readiness (YES / (YES+NO)):** {pct:.1f}% ({yes}/{denom})",
        "",
        "## Evidence quality (YES rows only)",
        "",
        f"- STRONG: {eq.get('STRONG', 0)}",
        f"- MODERATE: {eq.get('MODERATE', 0)}",
        f"- WEAK: {eq.get('WEAK', 0)}",
        "",
        f"**Weak/none evidence rows (all responses):** "
        f"{sum(1 for r in ledger.rows if r.evidence_strength in {EvidenceStrength.WEAK, EvidenceStrength.NONE})}",
        "",
        "## NO by remediation category",
        "",
    ]
    for cat, ids in sorted(no_by_cat.items(), key=lambda x: -len(x[1])):
        lines.append(f"- **{cat}** ({len(ids)}): {', '.join(ids[:15])}{'…' if len(ids) > 15 else ''}")
    lines.extend(
        [
            "",
            "## Production / provider gaps",
            "",
            "- Production PostgreSQL restore/recovery evidence: **not claimed** (SQLite drill labeled NON-PRODUCTION SQLITE DR EXERCISE only).",
            "- Incident response: **TABLETOP / SIMULATION** only — not production operational proof.",
            "- MFA, counsel-dependent privacy, endpoint attestations: remain open without fabricated attestations.",
            "",
            "## Verdict",
            "",
            f"**{verdict}**",
            "",
        ]
    )
    _READINESS.write_text("\n".join(lines), encoding="utf-8")


def _write_manifest(ledger: RemediationLedger, feature_sha: str) -> None:
    lines = [
        "# Submission evidence manifest — AI-CAIQ v1.1",
        "",
        f"Feature SHA: `{feature_sha}`",
        "",
        "Every YES below must be backed by repository or labeled exercise evidence.",
        "",
        "| Question ID | Answer | Strength | Evidence type | References |",
        "|-------------|--------|----------|---------------|------------|",
    ]
    for row in ledger.rows:
        if row.response != ControlAnswer.YES:
            continue
        refs = ", ".join(row.evidence_references[:5])
        if len(row.evidence_references) > 5:
            refs += "…"
        lines.append(
            f"| {row.question_id} | {row.response.value} | {row.evidence_strength.value} | "
            f"{row.evidence_type} | {refs} |"
        )
    lines.append("")
    lines.append(f"Total YES rows: {ledger.summary().get('YES', 0)}")
    _MANIFEST.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ledger = RemediationLedger.model_validate_json(_LEDGER_PATH.read_text(encoding="utf-8"))
    meta = json.loads(_INTEGRITY.read_text(encoding="utf-8"))
    feature_sha = (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_REPO, text=True).strip()
        if (_REPO / ".git").exists()
        else ledger.feature_sha
    )

    from scripts.csa_star_ai import export_final_workbook

    sys.argv = ["export_final_workbook", "--output", str(_FINAL_XLSX)]
    export_final_workbook.main()

    _write_readiness(ledger, meta, feature_sha)
    _write_manifest(ledger, feature_sha)
    print(f"Wrote {_FINAL_XLSX}, {_READINESS}, {_MANIFEST}")


if __name__ == "__main__":
    main()
