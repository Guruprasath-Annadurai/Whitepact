"""The MCP Trust/Supply-Chain Scanner (SPEC.md Section 7, Phase 13).

Scans a caller-supplied `McpServerManifest` — this package never
connects to a remote MCP server itself. That's a deliberate boundary:
actually speaking the MCP protocol to an arbitrary third-party server
(handshake, `tools/list`, following redirects/proxies) is real,
separate transport-layer work with its own trust and security
questions (SSRF risk in fetching an arbitrary URL server-side, for
one) — this module's job is the *analysis* once a caller already has
the tool list, not the fetching.

Three checks, each honestly scoped to what it can actually claim (see
`models.py`'s `Verdict`):

1. **Tool name/server name confusable-character check** — a bounded
   lookup table of Cyrillic/Greek characters that look like ASCII
   letters (the classic typosquat trick: "rai_scan" vs "rаi_scan" with
   a Cyrillic а). Deliberately *not* a full Unicode TR39 confusables
   implementation — that's real, separate, much larger work; this is a
   bounded, useful subset. Presence or absence of a listed confusable
   character is a fact about the string itself, so this is the one
   check that can return `VERIFIED_FACT` either way.
2. **Tool description content scan** — reuses the existing, tested
   `GuardrailsEngine` (the same regex-based PII/toxicity/custom-pattern
   detection already used everywhere else in this codebase) against
   every tool's description text, looking for injected-instruction
   patterns. Always `INFERRED_SIGNAL`: a match suggests something
   worth a human look, and a clean scan suggests nothing was found by
   *this* heuristic — neither is proof.
3. **Known public incident cross-reference** — an *optional* check
   (only runs if a `PublicIncidentRepository` is supplied) reusing the
   existing AI Incident Database's `check()` method. Filed incidents
   found -> `VERIFIED_FACT` (real, filed reports exist). None found ->
   `UNKNOWN`, not "safe" — a small or new server may simply not have
   been scrutinized yet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from responsibleai.guardrails.engine import GuardrailsEngine
from responsibleai.supplychain.models import (
    Finding,
    McpServerManifest,
    SupplyChainReport,
    Verdict,
)

if TYPE_CHECKING:
    from responsibleai.db.public_incident_repository import PublicIncidentRepository

# A bounded set of non-ASCII characters visually confusable with a
# common ASCII letter -- covers the Cyrillic/Greek homoglyphs most
# frequently seen in real npm/PyPI typosquatting incidents. Not
# exhaustive; see this module's docstring for why that's a stated
# limitation, not an oversight.
_CONFUSABLE_CHARS: dict[str, str] = {
    # Cyrillic lookalikes
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y",
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O",
    "Р": "P", "С": "C", "Т": "T", "Х": "X",
    # Greek lookalikes
    "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K",
    "Μ": "M", "Ν": "N", "Ο": "O", "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X",
    "ο": "o", "α": "a",
}


def _find_confusable_chars(text: str) -> list[dict[str, str]]:
    return [
        {"char": ch, "position": str(i), "looks_like": _CONFUSABLE_CHARS[ch]}
        for i, ch in enumerate(text)
        if ch in _CONFUSABLE_CHARS
    ]


class SupplyChainScanner:
    def __init__(self, guardrails: GuardrailsEngine | None = None) -> None:
        self._guardrails = guardrails or GuardrailsEngine()

    def _check_confusable_characters(self, manifest: McpServerManifest) -> Finding:
        hits: dict[str, list[dict[str, str]]] = {}
        server_hits = _find_confusable_chars(manifest.name)
        if server_hits:
            hits["server_name"] = server_hits
        for tool in manifest.tools:
            tool_hits = _find_confusable_chars(tool.name)
            if tool_hits:
                hits[f"tool:{tool.name}"] = tool_hits

        if hits:
            return Finding(
                check="confusable_characters",
                verdict=Verdict.VERIFIED_FACT,
                summary=(
                    f"{len(hits)} name(s) contain non-ASCII characters that "
                    "visually resemble common ASCII letters (a typosquatting pattern)."
                ),
                detail={"matches": hits},
            )
        return Finding(
            check="confusable_characters",
            verdict=Verdict.VERIFIED_FACT,
            summary="No known confusable characters found in the server or tool names.",
        )

    def _check_tool_descriptions(self, manifest: McpServerManifest) -> Finding:
        flagged: dict[str, list[str]] = {}
        for tool in manifest.tools:
            result = self._guardrails.scan(tool.description)
            if result.is_blocked:
                flagged[tool.name] = result.block_reasons

        if flagged:
            return Finding(
                check="tool_description_scan",
                verdict=Verdict.INFERRED_SIGNAL,
                summary=(
                    f"{len(flagged)} of {len(manifest.tools)} tool description(s) "
                    "matched a content pattern worth a human review."
                ),
                detail={"flagged_tools": flagged},
            )
        return Finding(
            check="tool_description_scan",
            verdict=Verdict.INFERRED_SIGNAL,
            summary=(
                f"No known-bad content patterns found across {len(manifest.tools)} "
                "tool description(s) -- not proof of safety, only that this "
                "heuristic scan found nothing."
            ),
        )

    async def _check_known_incidents(
        self, manifest: McpServerManifest, incident_repo: PublicIncidentRepository,
    ) -> Finding:
        incidents = await incident_repo.check(manifest.name, manifest.publisher or "")
        if incidents:
            return Finding(
                check="known_incidents",
                verdict=Verdict.VERIFIED_FACT,
                summary=f"{len(incidents)} publicly filed incident report(s) found for this system.",
                detail={"incidents": incidents},
            )
        return Finding(
            check="known_incidents",
            verdict=Verdict.UNKNOWN,
            summary=(
                "No public incident reports found for this system. This is not "
                "evidence of safety -- a new or low-visibility server may simply "
                "not have been reported on yet."
            ),
        )

    def scan_offline(self, manifest: McpServerManifest) -> list[Finding]:
        """The checks that need no I/O and no external repository."""
        return [
            self._check_confusable_characters(manifest),
            self._check_tool_descriptions(manifest),
        ]

    async def scan(
        self,
        manifest: McpServerManifest,
        *,
        incident_repo: PublicIncidentRepository | None = None,
    ) -> SupplyChainReport:
        findings = self.scan_offline(manifest)
        if incident_repo is not None:
            findings.append(await self._check_known_incidents(manifest, incident_repo))
        return SupplyChainReport(server_name=manifest.name, findings=findings)
