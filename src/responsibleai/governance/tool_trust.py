# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tool Trust Network (Authority Everywhere Phase 8) — a continuously
maintained trust score for one org-registered upstream MCP server,
independent of who is asking to call it.

This is a genuine generalization of two things that already existed
before this module: `supplychain/scanner.py`'s three-check scanner
(confusable characters, description content, known incidents) and
`governance/upstream.py`'s registry ("registration is the approval
step"). Neither of those, on its own, answers "should calls to this
server keep being allowed *right now*" — the scanner produces a report
a human has to read, and registration never changes once an admin
approves it. `ToolTrustScore` is the missing piece: a persisted,
queryable verdict that the request-time gate in
`mcp/upstream_dispatch.py` can actually check.

Scoped honestly: this is a deterministic, explainable score, not a
learned model — every point lost is traceable to a specific finding.
It does not attempt behavioral/runtime anomaly detection (repeated
unusual call patterns, response-content drift) — that's real, separate,
future work: this module scores what a supply-chain scan and incident
history already know, plus an explicit, audited admin override. See
`AUTHORITY_EVERYWHERE_CURRENT_STATE.md`'s classification of
`supplychain/scanner.py` as "ABSORB INTO AUTHORITY LAYER" for how this
fits the wider plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from responsibleai.supplychain.models import SupplyChainReport, Verdict

# The baseline every newly-registered, never-yet-scanned server starts
# at -- not TRUSTED (nothing has verified it yet) and not UNTRUSTED
# (nothing bad has been found either); PROVISIONAL reflects "admin
# already approved registration, no independent signal yet either way."
BASELINE_SCORE = 70

# A VERIFIED_FACT confusable-character hit is real evidence of a
# typosquatting pattern in the server's or a tool's own name -- the
# single strongest signal this module can act on, since it's a fact
# about the string itself, not a heuristic.
CONFUSABLE_CHARACTER_PENALTY = 40

# Each tool description flagged by the guardrails content scan is an
# INFERRED_SIGNAL (heuristic, not proof) -- weighted lower per-hit than
# the confusable-character check, and capped so one server with many
# tools can't be driven to zero by volume alone.
FLAGGED_DESCRIPTION_PENALTY = 15
FLAGGED_DESCRIPTION_PENALTY_CAP = 45

# A real, filed public incident report is the strongest possible
# negative signal this module has access to -- large enough that even
# a single filed incident drops a server out of TRUSTED range.
KNOWN_INCIDENT_PENALTY = 50

MIN_SCORE = 0
MAX_SCORE = 100

# A server that has never been scanned cannot reach TRUSTED purely by
# the passage of time -- TRUSTED requires a scan to have actually run
# at least once, so "nobody has looked yet" can never read the same as
# "this was checked and found good."
UNSCANNED_SCORE_CEILING = 79


class ToolTrustTier(StrEnum):
    """The bucket a numeric score maps to -- what
    `mcp/upstream_dispatch.py`'s gate actually branches on, not the raw
    number (the number is evidence for the tier, not itself a policy
    threshold callers should hardcode)."""

    TRUSTED = "TRUSTED"  # score >= 80, and has been scanned at least once
    PROVISIONAL = "PROVISIONAL"  # score 40-79 (or unscanned, capped below 80)
    UNTRUSTED = "UNTRUSTED"  # score 1-39
    BLOCKED = "BLOCKED"  # score == 0, or an explicit admin override


def _tier_for_score(score: int, *, has_been_scanned: bool) -> ToolTrustTier:
    if score <= MIN_SCORE:
        return ToolTrustTier.BLOCKED
    if score >= 80 and has_been_scanned:
        return ToolTrustTier.TRUSTED
    if score >= 40:
        return ToolTrustTier.PROVISIONAL
    return ToolTrustTier.UNTRUSTED


@dataclass
class ToolTrustScore:
    """One org-scoped upstream server's current trust standing. Built
    by `compute_trust_score()` (from a fresh scan) or by
    `apply_admin_override()` (from an explicit admin decision) — never
    constructed directly by request-time code, so every score in
    existence traces back to one of those two, auditable paths."""

    server_id: str
    org_id: str
    score: int
    tier: ToolTrustTier
    has_been_scanned: bool
    incident_count: int = 0
    scan_report_id: str | None = None
    scan_summary: str | None = None
    last_scanned_at: datetime | None = None
    admin_override_tier: ToolTrustTier | None = None
    admin_override_by: str | None = None
    admin_override_reason: str | None = None
    admin_override_at: datetime | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "server_id": self.server_id,
            "org_id": self.org_id,
            "score": self.score,
            "tier": self.tier.value,
            "has_been_scanned": self.has_been_scanned,
            "incident_count": self.incident_count,
            "scan_report_id": self.scan_report_id,
            "scan_summary": self.scan_summary,
            "last_scanned_at": self.last_scanned_at.isoformat() if self.last_scanned_at else None,
            "admin_override_tier": (
                self.admin_override_tier.value if self.admin_override_tier else None
            ),
            "admin_override_by": self.admin_override_by,
            "admin_override_reason": self.admin_override_reason,
            "admin_override_at": (
                self.admin_override_at.isoformat() if self.admin_override_at else None
            ),
            "updated_at": self.updated_at.isoformat(),
        }


def compute_trust_score(
    server_id: str,
    org_id: str,
    report: SupplyChainReport,
    *,
    incident_count: int = 0,
) -> ToolTrustScore:
    """Deterministic scoring from one `SupplyChainScanner.scan()` run.
    Every deduction below is traceable to a specific `Finding` -- this
    function does not invent signal the scan report doesn't contain.
    Admin overrides are layered on separately by
    `apply_admin_override()`, never inside this function, so a fresh
    scan can never silently clear an admin's explicit BLOCKED decision.
    """
    score = BASELINE_SCORE

    confusable = next((f for f in report.findings if f.check == "confusable_characters"), None)
    if confusable is not None and confusable.verdict is Verdict.VERIFIED_FACT and confusable.detail:
        score -= CONFUSABLE_CHARACTER_PENALTY

    description_scan = next(
        (f for f in report.findings if f.check == "tool_description_scan"), None
    )
    if description_scan is not None and description_scan.detail.get("flagged_tools"):
        flagged_count = len(description_scan.detail["flagged_tools"])
        score -= min(flagged_count * FLAGGED_DESCRIPTION_PENALTY, FLAGGED_DESCRIPTION_PENALTY_CAP)

    known_incidents = next((f for f in report.findings if f.check == "known_incidents"), None)
    if known_incidents is not None and known_incidents.verdict is Verdict.VERIFIED_FACT:
        score -= KNOWN_INCIDENT_PENALTY

    score = max(MIN_SCORE, min(MAX_SCORE, score))
    tier = _tier_for_score(score, has_been_scanned=True)

    return ToolTrustScore(
        server_id=server_id,
        org_id=org_id,
        score=score,
        tier=tier,
        has_been_scanned=True,
        incident_count=incident_count,
        scan_report_id=report.report_id,
        scan_summary=(
            f"{len(report.findings)} check(s) run; "
            f"{len(report.findings_by_verdict(Verdict.VERIFIED_FACT))} verified fact(s), "
            f"{len(report.findings_by_verdict(Verdict.INFERRED_SIGNAL))} inferred signal(s)."
        ),
        last_scanned_at=report.scanned_at,
    )


def unscanned_score(server_id: str, org_id: str) -> ToolTrustScore:
    """What a server has before any scan has ever run against it --
    PROVISIONAL, capped below the TRUSTED threshold regardless of the
    numeric baseline, per `UNSCANNED_SCORE_CEILING`'s own reasoning."""
    return ToolTrustScore(
        server_id=server_id,
        org_id=org_id,
        score=min(BASELINE_SCORE, UNSCANNED_SCORE_CEILING),
        tier=ToolTrustTier.PROVISIONAL,
        has_been_scanned=False,
        scan_summary="Never scanned.",
    )


def apply_admin_override(
    current: ToolTrustScore,
    tier: ToolTrustTier,
    *,
    admin_id: str,
    reason: str,
) -> ToolTrustScore:
    """An explicit, audited admin decision that overrides whatever the
    scan-derived score/tier would otherwise be — the one path that can
    set BLOCKED (a scan alone never fully zeroes a score, since
    `compute_trust_score()`'s penalties are individually bounded) or
    force TRUSTED ahead of what the deterministic scoring would grant.
    Every override carries who and why, non-optionally — an
    unattributed override would be worse than not having the escape
    hatch at all."""
    override_score = {
        ToolTrustTier.BLOCKED: MIN_SCORE,
        ToolTrustTier.TRUSTED: MAX_SCORE,
        ToolTrustTier.PROVISIONAL: BASELINE_SCORE,
        ToolTrustTier.UNTRUSTED: 20,
    }[tier]
    return ToolTrustScore(
        server_id=current.server_id,
        org_id=current.org_id,
        score=override_score,
        tier=tier,
        has_been_scanned=current.has_been_scanned,
        incident_count=current.incident_count,
        scan_report_id=current.scan_report_id,
        scan_summary=current.scan_summary,
        last_scanned_at=current.last_scanned_at,
        admin_override_tier=tier,
        admin_override_by=admin_id,
        admin_override_reason=reason,
        admin_override_at=datetime.now(UTC),
    )
