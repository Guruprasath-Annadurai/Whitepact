"""Memory Firewall (v3 authority-layer work, "Memory Authority"): a
deterministic scan for prompt-injection patterns aimed specifically at
persistent agent memory -- distinct from ``GuardrailsEngine``'s
PII/toxicity scan of arbitrary tool-call arguments.

**Why memory is a distinct risk, not just more content to scan**: a
toxic or PII-laden string in a normal tool call is seen once, by one
call. A poisoned write to persistent memory is replayed as *trusted
context* in every future session that reads it back -- an injection
payload that fails to affect the current turn can still succeed weeks
later once it's sitting in memory the model treats as its own prior
reasoning. That's the property this module exists to catch: text that
tries to look like an instruction, a role marker, or an override,
rather than like content *about* something.

**Honestly scoped**: WhitePact has no memory store of its own (no
``rai_memory_*`` tool existed before this). This is pure ``re``-module
pattern matching -- no LLM call, same "prefer deterministic security
controls" rule as ``GuardrailsEngine`` -- meant to be called by an
external memory system (a company's own vector DB, conversation log,
etc.) before it actually persists or serves content, via the
``rai_memory_write_check``/``rai_memory_read_check`` MCP tools
(``mcp/tools.py``) and the gateway wiring in ``governance/gateway.py``.
Not a general jailbreak/prompt-injection detector for arbitrary LLM
input -- deliberately narrow to patterns that specifically try to
inject a persistent instruction or fake conversational role, the
concrete risk memory poses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Each pattern targets a specific injection technique aimed at
# persistent memory, not generic "bad words" -- a memory-store user
# writing "the system administrator said to ignore the old policy" as
# a factual note is not what these should catch; "ignore all previous
# instructions" as an instruction to the model reading this memory back
# later is.
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

# All patterns are case-insensitive (an injection attempt capitalized
# at a sentence start is exactly as real as a lowercase one) and
# multiline (fake_role_marker's `^` must match the start of any line
# within the content, not just the start of the whole string).
_COMPILED_PATTERNS: dict[str, re.Pattern[str]] = {
    name: re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    for name, pattern in _INJECTION_PATTERNS.items()
}


@dataclass(frozen=True)
class MemoryFirewallResult:
    is_blocked: bool
    matched_patterns: tuple[str, ...]


def scan_memory_write(content: str) -> MemoryFirewallResult:
    """Scans *content* destined for persistent memory. Returns every
    matched pattern name (not just the first) -- callers/evidence
    records benefit from seeing the full match set, same reasoning as
    ``GuardrailsResult`` collecting every PII/toxicity finding rather
    than stopping at one."""
    matched = tuple(
        name for name, compiled in _COMPILED_PATTERNS.items() if compiled.search(content)
    )
    return MemoryFirewallResult(is_blocked=bool(matched), matched_patterns=matched)
