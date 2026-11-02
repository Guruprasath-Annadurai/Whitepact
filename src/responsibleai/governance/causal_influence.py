"""Causal Influence Firewall (Authority Everywhere Phase 7) —
generalizes `governance/memory_firewall.py`'s persistent-memory-only
injection scan into a provenance-aware check that runs against *any*
upstream content that causally shaped the current action, not just
content about to be written to memory.

**The gap this closes**: `memory_firewall.py` answers "does this one
string, about to be written to memory, contain a known injection
pattern." It never asks "where did the content that shaped *this
action's arguments* actually come from" — a tool-call argument built
from a prior tool's output, a sub-agent's returned result, or a scraped
web page carries exactly the same replay-as-trusted-context risk memory
does, and none of it was ever scanned unless it happened to also be a
memory write. This module generalizes both halves: the *what* (any
provenance entry's content, not just memory content, reusing the same
pattern table) and the *so what* (a provenance entry can also just be
tagged untrusted with no injection match at all — still worth recording
as a softer, non-blocking signal, since "shaped by unverified content"
is itself real signal even when nothing in it looks like an attack).

**Honestly scoped, the same way `memory_firewall.py` was**: this
platform does not sit inside an agent framework's reasoning loop and
cannot observe, on its own, what upstream content actually influenced a
given tool call — there is no runtime hook here to intercept an LLM's
context window. Like `memory_scope` on `AuthorityContext.constraints`
(see that class's own docstring: "argument-driven, not
action-type-gated... absent -> not applicable, never blocks"),
provenance must be *declared* by the caller — a framework adapter that
already tracks its own tool-call/sub-agent lineage passes it along via
the reserved `_provenance` argument key. No caller declaring it (every
caller before this module existed, and any caller not instrumented for
provenance tracking) — this check never fires, identical to prior
behavior.

**Not a general jailbreak/prompt-injection detector for arbitrary LLM
input**, same limitation `memory_firewall.py` states plainly: deliberately
narrow to patterns that specifically try to inject a persistent
instruction or fake conversational role — the concrete risk replayed,
causally-influential content poses, not a claim of catching every
possible injection technique.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

# Canonical location for this pattern table -- previously duplicated
# only in memory_firewall.py, which now delegates here (Phase 0's
# "ABSORB INTO AUTHORITY LAYER": generalize, don't replace). Each
# pattern targets a specific injection technique aimed at content that
# will be replayed as trusted context later, not generic "bad words" --
# see the original memory_firewall.py module docstring's own reasoning
# for why "the system administrator said to ignore the old policy" as
# a factual note is not what these should catch, while "ignore all
# previous instructions" as an instruction to whatever reads this
# content back is.
_INJECTION_PATTERNS: dict[str, str] = {
    "instruction_override": (
        r"\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+)?"
        r"(?:previous|prior|earlier|above)\s+instructions?\b"
    ),
    "role_override": r"\byou\s+are\s+now\s+(?:a|an|the)\b",
    "fake_role_marker": r"^\s*(?:system|assistant|developer)\s*:",
    "new_instructions": r"\bnew\s+instructions?\s*:",
    "act_as_override": r"\bact\s+as\s+(?:if\s+you\s+are\s+|a\s+|an\s+)?(?:a\s+different|unrestricted|dan)\b",
    "prompt_leak_attempt": r"\breveal\s+your\s+(?:system\s+prompt|instructions)\b",
}

# Case-insensitive (an injection attempt capitalized at a sentence
# start is exactly as real as a lowercase one) and multiline
# (fake_role_marker's `^` must match the start of any line within the
# content, not just the start of the whole string).
_COMPILED_PATTERNS: dict[str, re.Pattern[str]] = {
    name: re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    for name, pattern in _INJECTION_PATTERNS.items()
}


def scan_content_for_injection_patterns(content: str) -> tuple[str, ...]:
    """The shared pattern-matching primitive every content-bearing
    check in this module (and `memory_firewall.scan_memory_write()`)
    reuses. Returns every matched pattern name, not just the first."""
    return tuple(name for name, compiled in _COMPILED_PATTERNS.items() if compiled.search(content))


class ProvenanceKind(StrEnum):
    """What kind of upstream source a `ProvenanceEntry` describes —
    open to more kinds as real adapter needs arise (matches
    `docs/architecture/AUTHORITY_EVERYWHERE.md`'s own "adapters
    architected for, not built now" discipline: don't add a kind
    speculatively)."""

    MEMORY_READ = "memory_read"
    TOOL_OUTPUT = "tool_output"
    SUB_AGENT_RESULT = "sub_agent_result"
    USER_INPUT = "user_input"
    EXTERNAL_CONTENT = "external_content"


class TrustLevel(StrEnum):
    """A caller's own assertion about one provenance entry's
    trustworthiness — this module never infers trust itself (it has no
    way to independently verify a claim like "this came from our own
    verified config"), it only acts on what's declared."""

    TRUSTED = "TRUSTED"
    UNTRUSTED = "UNTRUSTED"
    # A caller that has provenance to report but genuinely doesn't know
    # the trust level (e.g. a generic sub-agent framework with no
    # verification step of its own) declares UNKNOWN rather than
    # guessing TRUSTED -- treated identically to UNTRUSTED for
    # `has_untrusted_influence` below, fail-closed by design.
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ProvenanceEntry:
    """One upstream source a caller asserts causally contributed to
    the current action. `content` is optional — an entry may assert
    only "this came from an untrusted sub-agent" without carrying
    scannable text (e.g. a binary tool result, or a caller unwilling to
    forward raw content through governance for its own reasons); such
    an entry still contributes to `has_untrusted_influence` even though
    it contributes nothing to the pattern scan."""

    kind: ProvenanceKind
    trust: TrustLevel
    content: str | None = None
    source_id: str | None = None


@dataclass(frozen=True)
class CausalInfluenceResult:
    is_blocked: bool
    matched_patterns: tuple[str, ...]
    matched_entry_kinds: tuple[ProvenanceKind, ...]
    has_untrusted_influence: bool
    untrusted_entry_kinds: tuple[ProvenanceKind, ...]


def parse_provenance(raw: Any) -> tuple[ProvenanceEntry, ...]:
    """Parses the reserved `_provenance` argument value (expected: a
    list of dicts with `kind`/`trust`/optional `content`/`source_id`
    keys) into `ProvenanceEntry` objects. Fail-safe, not fail-loud: a
    missing or malformed `_provenance` value, or one malformed entry
    within an otherwise-valid list, is silently dropped rather than
    raising — this is caller-supplied, best-effort metadata riding
    along in `arguments`, not a validated API contract; a caller that
    gets the shape wrong should see "no provenance considered" (the
    same as not declaring any), not a governance-evaluation crash.
    """
    if not isinstance(raw, list):
        return ()
    entries: list[ProvenanceEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        kind_raw = item.get("kind")
        trust_raw = item.get("trust")
        if not isinstance(kind_raw, str) or not isinstance(trust_raw, str):
            continue
        try:
            kind = ProvenanceKind(kind_raw)
            trust = TrustLevel(trust_raw)
        except ValueError:
            continue
        content = item.get("content")
        if content is not None and not isinstance(content, str):
            content = None
        source_id = item.get("source_id")
        if source_id is not None and not isinstance(source_id, str):
            source_id = None
        entries.append(
            ProvenanceEntry(kind=kind, trust=trust, content=content, source_id=source_id)
        )
    return tuple(entries)


def analyze_causal_influence(
    provenance: tuple[ProvenanceEntry, ...],
) -> CausalInfluenceResult:
    """Runs the injection-pattern scan across every provenance entry's
    content and separately tracks which entries are untrusted/unknown
    — two distinct signals, deliberately not collapsed into one. A
    caller (`gateway.py`) treats a pattern match as a hard block and
    mere untrusted presence as a softer, non-blocking, evidence-visible
    marker; see that module's own reasoning for keeping this first
    increment binary rather than also modulating risk tier, matching
    the same bounded-scope choice the Tool Trust Network gate made."""
    matched_patterns: set[str] = set()
    matched_kinds: list[ProvenanceKind] = []
    untrusted_kinds: list[ProvenanceKind] = []

    for entry in provenance:
        if entry.trust is not TrustLevel.TRUSTED:
            untrusted_kinds.append(entry.kind)
        if entry.content:
            hits = scan_content_for_injection_patterns(entry.content)
            if hits:
                matched_patterns.update(hits)
                matched_kinds.append(entry.kind)

    return CausalInfluenceResult(
        is_blocked=bool(matched_patterns),
        matched_patterns=tuple(sorted(matched_patterns)),
        matched_entry_kinds=tuple(matched_kinds),
        has_untrusted_influence=bool(untrusted_kinds),
        untrusted_entry_kinds=tuple(untrusted_kinds),
    )
