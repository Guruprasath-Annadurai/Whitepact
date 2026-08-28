"""Tests for Security Remediation Gap 7 (ExecutionAuthorization
trust-boundary review). See
`docs/enterprise-neural/REMEDIATION_GAP7_EXECUTION_AUTHORIZATION_BOUNDARY.md`.

`ExecutionAuthorization` is deliberately unsigned because it is
assumed to never cross a process boundary (`governance/execution.py`'s
own module docstring). That assumption was treated as a hypothesis,
searched exhaustively, and holds today -- but "no one currently
serializes it" is a fact about current call sites, not a structural
guarantee: a plain dataclass is picklable by Python's default protocol
regardless of intent. These tests are the regression guard the
directive asks for: prevent future accidental serialization or
boundary crossing from landing unnoticed, rather than re-proving the
current absence (which CODEX_REVIEW_HANDOFF.md Sec 9 and this gap's
own report already did by direct inspection).
"""

from __future__ import annotations

import re
from pathlib import Path

from responsibleai.governance.execution import ExecutionAuthorization

_SRC_ROOT = Path(__file__).parent.parent / "src" / "responsibleai"

_KNOWN_AUTHORIZE_EXECUTION_CALL_SITES = frozenset(
    {
        _SRC_ROOT / "mcp" / "upstream_dispatch.py",
        _SRC_ROOT / "mcp" / "governance_integration.py",
    }
)

# Any of these appearing in a file that also references
# ExecutionAuthorization is a signal the process-local assumption may
# have been broken -- not proof by itself (a false positive is
# possible, e.g. an unrelated pickle import in the same file used for
# something else entirely), but exactly the kind of thing that should
# force a human to look, not pass silently.
_BOUNDARY_CROSSING_PRIMITIVES = (
    "pickle.",
    "json.dumps",
    "redis.",
    "celery",
    "Queue(",
    "multiprocessing",
    "subprocess.",
    "httpx.post",
    "httpx.AsyncClient",
    "aioredis",
)


def _files_referencing(name: str) -> list[Path]:
    pattern = re.compile(rf"\b{re.escape(name)}\b")
    hits = []
    for path in _SRC_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        if pattern.search(path.read_text(encoding="utf-8")):
            hits.append(path)
    return hits


def _real_call_sites(function_name: str) -> list[Path]:
    """Every file with a real call to `function_name(` -- excludes the
    `def function_name(` line itself, backtick-quoted docstring
    mentions (`` `function_name()` ``), and `#`-comment-line mentions,
    but (unlike Phase 11's line-start-anchored version) does match
    `x = function_name(...)`, since authorize_execution()'s own call
    sites always assign the result."""
    call_pattern = re.compile(rf"(?<!def )(?<!`){re.escape(function_name)}\(")
    hits = []
    for path in _SRC_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if call_pattern.search(line) and not line.strip().startswith("#"):
                hits.append(path)
                break
    return hits


class TestAuthorizeExecutionCallSitesAreExactlyTheAuditedSet:
    def test_no_new_call_site_of_authorize_execution(self) -> None:
        hits = set(_real_call_sites("authorize_execution"))
        # governance/execution.py itself contains the def line and two
        # backtick-quoted docstring mentions, none of which
        # _real_call_sites() counts as a real call (see its own
        # docstring for exactly what it excludes and why).
        assert hits == _KNOWN_AUTHORIZE_EXECUTION_CALL_SITES, (
            f"authorize_execution() called from an unaudited location: "
            f"{hits - _KNOWN_AUTHORIZE_EXECUTION_CALL_SITES} -- if this is "
            "intentional, review whether ExecutionAuthorization can now "
            "cross a process boundary before updating this guard."
        )


# Reviewed, individually-justified exceptions -- each verified by
# reading the actual code before being added here, not blanket-excused.
# A NEW (file, primitive) pair not in this set still fails the test.
_REVIEWED_FALSE_POSITIVES: dict[Path, frozenset[str]] = {
    # json.dumps() here serializes the MCP tool-call response payload
    # (a plain dict), never an ExecutionAuthorization instance.
    _SRC_ROOT / "mcp" / "server.py": frozenset({"json.dumps"}),
    # httpx.AsyncClient is the outbound HTTP client used to proxy the
    # already-authorized tool call to the upstream MCP server, using a
    # resolved credential string (JIT credential) -- never the
    # ExecutionAuthorization object itself, which stays local.
    _SRC_ROOT / "governance" / "upstream_executor.py": frozenset({"httpx.AsyncClient"}),
    # json.dumps() here canonically serializes a HeartVetoRecord-related
    # payload for hashing -- ExecutionAuthorization is only mentioned in
    # this module's docstring, never constructed or passed through it.
    _SRC_ROOT / "governance" / "legitimacy_envelope.py": frozenset({"json.dumps"}),
    # json.dumps() here canonically serializes AuthorityGrant's own
    # fields -- ExecutionAuthorization is only mentioned in a comment
    # ("mirrors ExecutionAuthorization's own existing TTL pattern").
    _SRC_ROOT / "governance" / "authority_grant.py": frozenset({"json.dumps"}),
}


class TestNoBoundaryCrossingPrimitiveNearExecutionAuthorization:
    def test_no_file_referencing_execution_authorization_also_serializes_or_queues_it(
        self,
    ) -> None:
        referencing_files = _files_referencing("ExecutionAuthorization")
        assert referencing_files, "sanity check: the class itself must be findable"

        offenders: dict[Path, list[str]] = {}
        for path in referencing_files:
            text = path.read_text(encoding="utf-8")
            found = [
                p
                for p in _BOUNDARY_CROSSING_PRIMITIVES
                if p in text and p not in _REVIEWED_FALSE_POSITIVES.get(path, frozenset())
            ]
            if found:
                offenders[path] = found

        assert not offenders, (
            f"Files referencing ExecutionAuthorization also contain a "
            f"boundary-crossing primitive: {offenders} -- if this is a "
            "false positive (the primitive is unrelated to "
            "ExecutionAuthorization in that file), confirm by reading it; "
            "if it's real, ExecutionAuthorization needs cryptographic "
            "signing before it can safely cross that boundary."
        )


class TestExecutionAuthorizationHasNoSerializationSupport:
    def test_no_to_dict_or_asdict_style_method(self) -> None:
        for name in ("to_dict", "asdict", "to_json", "serialize"):
            assert not hasattr(ExecutionAuthorization, name), (
                f"ExecutionAuthorization gained a {name}() method -- this is "
                "exactly the kind of change that should trigger a fresh "
                "trust-boundary review (see the Gap 7 report), not land "
                "silently."
            )

    def test_no_custom_reduce_method(self) -> None:
        """A custom __reduce__/__reduce_ex__ would mean someone
        deliberately made this class more picklable/transportable than
        a default dataclass -- worth noticing if it happens."""
        assert "__reduce__" not in ExecutionAuthorization.__dict__
        assert "__reduce_ex__" not in ExecutionAuthorization.__dict__
