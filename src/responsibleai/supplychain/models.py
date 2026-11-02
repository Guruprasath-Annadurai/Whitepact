"""Domain models for the MCP Trust/Supply-Chain Scanner (SPEC.md
Section 7, Phase 13). SPEC.md's one hard requirement for this
subsystem: it "must distinguish VERIFIED FACT / INFERRED SIGNAL /
UNKNOWN per input, not produce a single opaque score." Every check in
`scanner.py` returns one of these three, and a `SupplyChainReport` is a
list of them — never collapsed into a 0-100 number a client might
mistake for a certification.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class Verdict(StrEnum):
    """What a single check can honestly claim about its result."""

    VERIFIED_FACT = "VERIFIED_FACT"  # a claim this check can stand behind directly
    INFERRED_SIGNAL = "INFERRED_SIGNAL"  # a heuristic result -- suggestive, not proof
    UNKNOWN = "UNKNOWN"  # no data either way; absence of evidence is not evidence of absence


@dataclass
class Finding:
    check: str  # stable identifier, e.g. "known_incidents", "tool_description_scan"
    verdict: Verdict
    summary: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "verdict": self.verdict.value,
            "summary": self.summary,
            "detail": self.detail,
        }


@dataclass
class McpToolDescriptor:
    """The minimum shape of an MCP tool needed to scan it -- deliberately
    not `mcp.types.Tool` itself, so this package stays independent of
    which MCP SDK version a caller happens to have installed."""

    name: str
    description: str


@dataclass
class McpServerManifest:
    """What a caller supplies about the MCP server being evaluated.
    Built by the caller from whatever they already know (an MCP
    `tools/list` response, a registry listing, ...) -- this scanner
    never itself connects to a remote MCP server; see `scanner.py`'s
    module docstring for why that's a deliberate boundary, not a gap.
    """

    name: str
    publisher: str | None = None
    tools: list[McpToolDescriptor] = field(default_factory=list)


@dataclass
class SupplyChainReport:
    server_name: str
    findings: list[Finding]
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    scanned_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def findings_by_verdict(self, verdict: Verdict) -> list[Finding]:
        return [f for f in self.findings if f.verdict is verdict]

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "server_name": self.server_name,
            "scanned_at": self.scanned_at.isoformat(),
            "findings": [f.to_dict() for f in self.findings],
        }
