# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Keep the README quickstart runnable and in sync with examples/."""

from __future__ import annotations

import re
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "quickstart_governance.py"


def test_quickstart_example_runs_and_prints_expected_decisions(capsys) -> None:
    runpy.run_path(str(EXAMPLE), run_name="__main__")
    out = capsys.readouterr().out
    assert "mcp_tool_call -> ALLOW" in out
    assert "deployment -> REQUIRE_APPROVAL" in out
    assert "payment -> DENY" in out


def test_readme_first_python_block_is_the_quickstart_and_runs() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    first_block = re.search(r"```python\n(.*?)```", readme, re.S)
    assert first_block is not None
    code = first_block.group(1)
    assert "WhitePactRuntimeGateway" in code
    exec(compile(code, "README.md:quickstart", "exec"), {"__name__": "__readme__"})
