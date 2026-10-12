# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Structural guard for REC-25: no route may mutate policy without going through the governance gate.

If someone adds a new route (or a new module) that changes ``governance_policies`` directly, tiered policy
governance would silently stop covering it. These checks fail the build instead.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "responsibleai"
MUTATORS = {"add_rule", "remove_rule", "reorder"}


def _functions(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef):
            yield node


def _calls_on_policy_repo(fn) -> list[str]:
    found: list[str] = []
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in MUTATORS
        ):
            owner = ast.unparse(node.func.value)
            if "_policy_repo" in owner:
                found.append(node.func.attr)
    return found


def test_every_dashboard_route_that_mutates_policy_calls_the_gate() -> None:
    tree = ast.parse((SRC / "dashboard" / "app.py").read_text())
    mutating = [(fn.name, _calls_on_policy_repo(fn)) for fn in _functions(tree)]
    mutating = [(name, calls) for name, calls in mutating if calls]
    assert {name for name, _ in mutating} == {
        "governance_add_policy_rule",
        "governance_remove_policy_rule",
        "governance_reorder_policy",
        "web_add_policy_rule",
        "web_remove_policy_rule",
        "web_reorder_policy",
    }, mutating
    for fn in _functions(tree):
        if fn.name in {name for name, _ in mutating}:
            called = {ast.unparse(n.func) for n in ast.walk(fn) if isinstance(n, ast.Call)}
            assert "_gate_policy_change" in called, f"{fn.name} mutates policy without the gate"
            kw = [
                k.arg
                for n in ast.walk(fn)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr in MUTATORS
                for k in n.keywords
            ]
            assert "expected_version" in kw, (
                f"{fn.name} applies the edit without the approved version"
            )


def test_no_other_module_mutates_the_policy_repository_or_activates_lifecycle_revisions() -> None:
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        rel = path.relative_to(SRC).as_posix()
        if rel in {
            "dashboard/app.py",  # reviewed above
            "db/policy_repository.py",  # the repository itself
            "governance/policy_lifecycle.py",  # the lifecycle manager itself (not wired to a route)
        }:
            continue
        text = path.read_text()
        tree = ast.parse(text)
        for fn in _functions(tree):
            if _calls_on_policy_repo(fn):
                offenders.append(f"{rel}:{fn.name} mutates via a policy repository")
        if "PolicyLifecycleManager" in text and "import" in text:
            offenders.append(f"{rel} uses PolicyLifecycleManager")
        if "governance_policies" in text and rel not in {"db/engine.py"}:
            if any(
                w in text
                for w in (
                    "insert(governance_policies",
                    "delete(governance_policies",
                    "update(governance_policies",
                )
            ):
                offenders.append(f"{rel} writes governance_policies directly")
    # Data-governance erasure and restore reconciliation legitimately delete tenant rows wholesale.
    offenders = [o for o in offenders if not o.startswith(("data_governance/",))]
    assert offenders == [], offenders


def test_the_lifecycle_manager_is_not_reachable_from_any_route() -> None:
    tree = ast.parse((SRC / "dashboard" / "app.py").read_text())
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert "PolicyLifecycleManager" not in names, (
        "PolicyLifecycleManager is now used by a route: wire it through the policy governance gate "
        "and update this test and register REC-25"
    )


@pytest.mark.parametrize("mode", ["single_admin", "tiered"])
def test_the_governance_mode_setting_exists_and_defaults_to_single_admin(mode: str) -> None:
    from responsibleai.dashboard.config import Settings

    assert Settings(_env_file=None).policy_governance_mode == "single_admin"
    assert Settings(_env_file=None, policy_governance_mode=mode).policy_governance_mode == mode
