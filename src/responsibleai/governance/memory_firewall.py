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

**Now a thin wrapper over `governance/causal_influence.py`** (Authority
Everywhere Phase 7): the actual pattern table and matching logic moved
there as the canonical, generalized location -- this module's public
API (`scan_memory_write`, `MemoryFirewallResult`) is unchanged, and
every existing caller (``mcp/tools.py``'s ``rai_memory_write_check``,
``governance/gateway.py``'s memory-write hard-block check) keeps
working exactly as before. What changed is scope, not behavior: memory
writes are one *kind* of causally-influential content now, not a
special case with its own copy of the pattern table. See
`causal_influence.py`'s module docstring for what generalized (any
upstream content, not just memory) and what didn't (still pure
``re``-module matching, still caller-declared, still not a general
jailbreak detector).
"""

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.governance.causal_influence import scan_content_for_injection_patterns


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
    matched = scan_content_for_injection_patterns(content)
    return MemoryFirewallResult(is_blocked=bool(matched), matched_patterns=matched)
