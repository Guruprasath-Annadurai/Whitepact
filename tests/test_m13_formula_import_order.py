# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Fresh process imports must not depend on previous test collection order."""

import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "modules",
    [
        "responsibleai.formula.serialization,responsibleai.formula.graph",
        "responsibleai.formula.graph,responsibleai.formula.serialization",
    ],
)
def test_formula_public_modules_import_independently(modules):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import importlib; [importlib.import_module(m) for m in {modules!r}.split(',')]",
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
