"""Heart Enforcement Chokepoint Closure, Phase E5.

`mcp.tools._dispatch_tool_unchecked()` (renamed from the previously
public-looking `dispatch_tool`) runs a tool's handler directly with no
authority, governance, or Heart legitimacy check of any kind. It
cannot be made literally uncallable from arbitrary in-process Python
(nothing in the language enforces that), so the property this test
actually protects is durability of the AUDIT, not impossibility of the
bypass: exactly two call sites are known and reasoned about today
(`mcp/server.py`'s stdio path, `governance/execution.py`'s
`InternalToolExecutor.execute()`, which requires a validated
`ExecutionAuthorization` first) -- a third call site appearing
anywhere else in this codebase would mean some new code path reaches
raw tool execution without going through that authorization, and this
test turns that into a loud, immediate CI failure instead of a silent
new bypass nobody notices.

Same heuristic (text-scan, not full AST/import-graph analysis),
documented as such, as `test_brain_policy_risk_boundary.py`'s
`classify_action_risk()`/`Policy.evaluate()` guards -- this file
deliberately mirrors that one's structure rather than inventing a new
pattern.
"""

from __future__ import annotations

import re
from pathlib import Path

_SRC_ROOT = Path(__file__).parent.parent / "src" / "responsibleai"


def _real_call_sites(pattern_text: str, defining_file: Path) -> list[Path]:
    """Every `.py` file under `_SRC_ROOT` containing an ACTUAL call
    matching `pattern_text` (not just a prose mention of the function
    name in a comment/docstring -- this function has extensive
    documentation referencing it by name elsewhere in this codebase,
    which a bare substring search would misfire on), other than
    `defining_file` itself."""
    pattern = re.compile(pattern_text)
    hits = []
    for path in _SRC_ROOT.rglob("*.py"):
        if path == defining_file:
            continue
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            hits.append(path)
    return hits


class TestDispatchToolUncheckedKnownCallSites:
    def test_only_the_two_audited_call_sites_exist(self) -> None:
        defining_file = _SRC_ROOT / "mcp" / "tools.py"
        hits = _real_call_sites(r"\bawait\s+_dispatch_tool_unchecked\(", defining_file)
        known = {
            _SRC_ROOT / "mcp" / "server.py",
            _SRC_ROOT / "governance" / "execution.py",
        }
        unexpected = [h for h in hits if h not in known]
        assert unexpected == [], (
            f"_dispatch_tool_unchecked() called from unaudited location(s): {unexpected} -- "
            "every new call site is a potential ungoverned execution path. If this is "
            "intentional, it needs its own authority/governance reasoning (see "
            "governance/execution.py's InternalToolExecutor for the pattern), not just "
            "adding a name to this allowlist."
        )
        assert set(hits) == known, (
            f"expected call sites {known}, found {set(hits)} -- "
            "one of the two known call sites may have been removed or renamed; "
            "update this test deliberately if that's intentional."
        )

    def test_the_function_is_not_re_exported_from_any_package_init(self) -> None:
        """It should never become one `from responsibleai import ...`
        or `from responsibleai.mcp import ...` away from looking like a
        normal public API -- confirms it stays reachable only via the
        explicit, deliberate `from responsibleai.mcp.tools import
        _dispatch_tool_unchecked` a caller has to write out in full."""
        for init_file in _SRC_ROOT.rglob("__init__.py"):
            text = init_file.read_text(encoding="utf-8")
            assert "_dispatch_tool_unchecked" not in text, (
                f"{init_file} re-exports _dispatch_tool_unchecked -- this would make it "
                "reachable via a shorter, more public-looking import path."
            )

    def test_no_module_level_alias_hides_the_underscore(self) -> None:
        """A line like `dispatch_tool = _dispatch_tool_unchecked` would
        silently recreate the old, public-looking name -- guards
        against exactly that regression."""
        for path in _SRC_ROOT.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            assert not re.search(r"^\s*dispatch_tool\s*=", text, re.MULTILINE), (
                f"{path} defines a bare 'dispatch_tool' alias -- this recreates the "
                "public-looking name Phase E5 deliberately removed."
            )
