# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WS-2 static invariant: consequential ``dispatch_tool`` invocation sites
must live only in explicitly reviewed canonical execution modules (BLK-P0-03)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_REPO_SRC = Path(__file__).resolve().parents[1] / "src" / "responsibleai"

# Modules allowed to invoke ``dispatch_tool`` (definition + canonical dispatch).
_DISPATCH_TOOL_ALLOWLIST = frozenset(
    {
        "mcp/tools.py",
        "governance/execution.py",
        "mcp/server.py",
        "isolation/subprocess_backend.py",
        "isolation/container_backend.py",
    }
)

# Modules allowed to call ``executor.execute(authorization, ...)`` on governed executors.
_EXECUTOR_EXECUTE_ALLOWLIST = frozenset(
    {
        "mcp/governance_integration.py",
        "mcp/upstream_dispatch.py",
        "governance/execution.py",
        "governance/upstream_executor.py",
    }
)


def _relative(path: Path) -> str:
    return str(path.relative_to(_REPO_SRC)).replace("\\", "/")


def _call_sites(path: Path, callee: str) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[tuple[int, str]] = []

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Name) and node.func.id == callee:
                hits.append((node.lineno, callee))
            elif isinstance(node.func, ast.Attribute) and node.func.attr == callee:
                hits.append((node.lineno, f".{callee}"))
            self.generic_visit(node)

    Visitor().visit(tree)
    return hits


@pytest.mark.parametrize("callee,allowlist", [("dispatch_tool", _DISPATCH_TOOL_ALLOWLIST)])
def test_consequential_dispatch_call_sites_are_allowlisted(callee: str, allowlist: frozenset[str]) -> None:
    violations: list[str] = []
    for py_file in sorted(_REPO_SRC.rglob("*.py")):
        rel = _relative(py_file)
        for lineno, _ in _call_sites(py_file, callee):
            if rel not in allowlist:
                violations.append(f"{rel}:{lineno}")
    assert not violations, (
        "New direct consequential dispatch detected outside canonical execution layer. "
        "Either route through governance/execution + governance_integration, or add an "
        f"explicit WS-2 review entry to the allowlist. Offenders: {violations}"
    )


def test_executor_execute_call_sites_are_allowlisted() -> None:
    violations: list[str] = []
    for py_file in sorted(_REPO_SRC.rglob("*.py")):
        rel = _relative(py_file)
        for lineno, _ in _call_sites(py_file, "execute"):
            if "execute(" not in py_file.read_text(encoding="utf-8"):
                continue
            # Only flag ``executor.execute`` / ``await executor.execute`` style calls.
            line = py_file.read_text(encoding="utf-8").splitlines()[lineno - 1]
            if "executor.execute" not in line.replace(" ", ""):
                continue
            if rel not in _EXECUTOR_EXECUTE_ALLOWLIST:
                violations.append(f"{rel}:{lineno}")
    assert not violations, (
        "Governed executor.execute() must not be introduced outside reviewed modules. "
        f"Offenders: {violations}"
    )
