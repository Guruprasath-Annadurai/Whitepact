# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Exact approved setup relationship; historical attack logic remains immutable."""

import ast
import hashlib
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tests/test_durable_lifecycle_state_provider.py"
ARCHIVE = ROOT / "tests/historical_evidence/durable_lifecycle_state_provider_before_stage3.py.txt"
ORIGINAL_COMMIT = "f03754a982043e8ffc33664b8b5cedff0564d906"
ORIGINAL_BLOB = "67edfa3ac80b182e784f6e94ae2e5a6ea30744a1"
REVISED_BLOB = "246240df9297248cf7ecc0407961cca129a38698"
TEST = "test_durable_store_b_failure_matrix"


def _blob(content):
    return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()


def _verify_relationship(original, revised):
    if _blob(original) != ORIGINAL_BLOB or _blob(revised) != REVISED_BLOB:
        raise ValueError("Unknown historical source or unapproved revision")
    old, new = ast.parse(original), ast.parse(revised)
    old_functions = {node.name: node for node in old.body if isinstance(node, ast.AsyncFunctionDef)}
    new_functions = {node.name: node for node in new.body if isinstance(node, ast.AsyncFunctionDef)}
    if old_functions.keys() != new_functions.keys():
        raise ValueError("Historical test identifiers changed")
    for name, before in old_functions.items():
        after = new_functions[name]
        if name != TEST:
            if ast.dump(before) != ast.dump(after):
                raise ValueError("Unapproved historical function change")
            if ast.get_source_segment(original.decode(), before) != ast.get_source_segment(
                revised.decode(), after
            ):
                raise ValueError("Unapproved historical source change")
        else:
            if ast.get_docstring(before) != ast.get_docstring(after):
                raise ValueError("Historical test objective changed")
            if [arg.arg for arg in after.args.args] != ["tmp_path", "controller"]:
                raise ValueError("Unapproved fixture signature")
            # Everything from the first original attack onward must be exactly
            # unchanged, including comments, exception matches and assertions.
            marker = b"    # 2. Advance to TOMBSTONED"
            old_tail = (
                ast.get_source_segment(original.decode(), before).encode().split(marker, 1)[1]
            )
            new_tail = ast.get_source_segment(revised.decode(), after).encode().split(marker, 1)[1]
            if old_tail != new_tail:
                raise ValueError("Historical attack sequence changed")
            if not any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_protected_failure_matrix_setup"
                for node in ast.walk(after)
            ):
                raise ValueError("Protected provisioning setup missing")


def test_approved_setup_has_exact_original_source_and_unchanged_attacks():
    source = subprocess.run(
        ["git", "show", f"{ORIGINAL_COMMIT}:tests/test_durable_lifecycle_state_provider.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    assert ARCHIVE.read_bytes() == source
    _verify_relationship(source, TARGET.read_bytes())


@pytest.mark.parametrize("tamper", [b"\nassert True\n", b"\n# noqa\n", b"\n# timeout override\n"])
def test_relationship_rejects_unapproved_content(tamper):
    with pytest.raises(ValueError, match="unapproved revision"):
        _verify_relationship(ARCHIVE.read_bytes(), TARGET.read_bytes() + tamper)


def test_relationship_requires_recoverable_original_evidence():
    with pytest.raises(ValueError, match="historical source"):
        _verify_relationship(b"", TARGET.read_bytes())
