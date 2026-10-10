# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""The security-fix inclusion gate must not be satisfiable by cosmetic evidence.

Each case builds a tiny tree containing one control, then mutates it the way a careless
merge, a refactor, or a deliberate cover-up would, and asserts the gate notices.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_security_fix_inclusion.py"

_spec = importlib.util.spec_from_file_location("check_security_fix_inclusion", SCRIPT)
assert _spec is not None and _spec.loader is not None
gate = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = gate
_spec.loader.exec_module(gate)

CONTROL = {
    "X-01-demo": {
        "files": ["src/impl.py"],
        "markers": ["enforce_boundary"],
        "tests": ["tests/test_demo.py"],
        "test_markers": ["test_boundary_is_enforced"],
    }
}
GOOD_IMPL = "def enforce_boundary(x):\n    return x\n"
GOOD_TEST = "def test_boundary_is_enforced():\n    assert enforce_boundary(1) == 1\n"
EXECUTED = {"test_boundary_is_enforced"}


def _tree(tmp_path: Path, impl: str = GOOD_IMPL, test: str = GOOD_TEST) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "impl.py").write_text(impl)
    (tmp_path / "tests" / "test_demo.py").write_text(test)
    return tmp_path


def _kinds(root: Path, executed: set[str] = EXECUTED) -> list[str]:
    report = gate.evaluate(root, CONTROL, executed)
    return [m["kind"] for m in report["missing"]]  # type: ignore[index]


def test_a_complete_control_passes(tmp_path: Path) -> None:
    assert _kinds(_tree(tmp_path)) == []


def test_the_real_tree_passes() -> None:
    report = gate.evaluate()
    assert report["passed"], report["missing"]


def test_deleted_implementation_is_detected(tmp_path: Path) -> None:
    assert "implementation" in _kinds(_tree(tmp_path, impl="def other():\n    pass\n"))


def test_marker_surviving_only_in_a_comment_is_detected(tmp_path: Path) -> None:
    """The original P1-04 control was 'verified' by an explanatory comment."""
    root = _tree(tmp_path, impl="# enforce_boundary used to live here\ndef other():\n    pass\n")
    assert "implementation" in _kinds(root)


def test_marker_in_a_string_or_code_still_counts(tmp_path: Path) -> None:
    root = _tree(tmp_path, impl='MESSAGE = "enforce_boundary denied"\n')
    assert _kinds(root) == []


def test_missing_regression_test_is_detected(tmp_path: Path) -> None:
    assert "regression-function" in _kinds(
        _tree(tmp_path, test="def test_other():\n    assert 1\n")
    )


def test_empty_regression_test_is_vacuous(tmp_path: Path) -> None:
    root = _tree(tmp_path, test="def test_boundary_is_enforced():\n    pass\n")
    assert "regression-vacuous" in _kinds(root)


@pytest.mark.parametrize(
    "decorator",
    [
        "@pytest.mark.skip(reason='x')",
        "@pytest.mark.skipif(True, reason='x')",
        "@pytest.mark.xfail",
    ],
)
def test_skipped_or_xfailed_regression_test_is_vacuous(tmp_path: Path, decorator: str) -> None:
    test = f"import pytest\n{decorator}\ndef test_boundary_is_enforced():\n    assert 1\n"
    assert "regression-vacuous" in _kinds(_tree(tmp_path, test=test))


def test_pytest_raises_counts_as_an_assertion(tmp_path: Path) -> None:
    test = (
        "import pytest\n"
        "def test_boundary_is_enforced():\n"
        "    with pytest.raises(ValueError):\n"
        "        raise ValueError\n"
    )
    assert _kinds(_tree(tmp_path, test=test)) == []


def test_regression_test_the_behavioural_gate_never_runs_is_detected(tmp_path: Path) -> None:
    assert "regression-not-executed" in _kinds(_tree(tmp_path), executed=set())


def test_every_declared_regression_function_is_executed_by_the_behavioural_gate() -> None:
    """Declared == executed, for the real controls."""
    executed = gate._behavioural_nodes()
    declared = {
        marker
        for spec in gate.CONTROLS.values()
        for marker in spec["test_markers"]
        if marker.startswith("test_")
    }
    assert declared <= executed, sorted(declared - executed)
