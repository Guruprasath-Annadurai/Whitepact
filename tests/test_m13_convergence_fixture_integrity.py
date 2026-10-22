# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Retain historical assertions while correcting authorized fixture prerequisites."""

import ast
import subprocess
from pathlib import Path

import pytest

REFERENCE = "e4f3f12862712762f0d16d561afbd195067606e3"
ROOT = Path(__file__).resolve().parents[1]


def original(path):
    return ast.parse(
        subprocess.check_output(["git", "show", f"{REFERENCE}:{path}"], cwd=ROOT, text=True)
    )


def assertions(tree):
    return [ast.dump(node) for node in ast.walk(tree) if isinstance(node, ast.Assert)]


def assert_preserved(old, new):
    remaining = iter(new)
    for assertion in old:
        assert any(candidate == assertion for candidate in remaining), assertion


@pytest.mark.parametrize(
    "path",
    [
        "tests/test_m13_titan_root_adversarial.py",
        "tests/test_m13_titan_authority_closure.py",
    ],
)
def test_root_fixture_corrections_preserve_every_original_assertion(path):
    revised = ast.parse((ROOT / path).read_text())
    functions = {node.name: node for node in revised.body if isinstance(node, ast.AsyncFunctionDef)}
    for node in original(path).body:
        if isinstance(node, ast.AsyncFunctionDef):
            assert_preserved(assertions(node), assertions(functions[node.name]))


def test_assertion_integrity_rejects_replacement_or_removal():
    with pytest.raises(AssertionError):
        assert_preserved(["original", "denial"], ["original", "allow"])
    with pytest.raises(AssertionError):
        assert_preserved(["original", "denial"], ["denial", "original"])


def test_startup_fixture_preserves_original_security_assertions():
    path = "tests/test_restore_admission_chokepoint.py"
    current = ast.parse((ROOT / path).read_text())
    functions = {node.name: node for node in current.body if isinstance(node, ast.AsyncFunctionDef)}
    for node in original(path).body:
        if isinstance(node, ast.AsyncFunctionDef):
            assert_preserved(assertions(node), assertions(functions[node.name]))


def test_recovery_disposition_preserves_neighboring_customer_tests():
    path = "tests/test_customer_real_approval_journey.py"
    current = {
        node.name: ast.dump(node)
        for node in ast.parse((ROOT / path).read_text()).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for node in original(path).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == "test_real_database_outage_blocks_new_admission_and_recovers":
                continue
            assert current[node.name] == ast.dump(node), node.name
