# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Diagnostic selection must not silently disable qualification coverage."""

import pytest
from scripts.engineering.m13_pg16_test_runner import pytest_arguments


def test_qualification_preserves_default_coverage():
    arguments = pytest_arguments(["tests/test_example.py"], False)
    assert arguments[1:] == ["-m", "pytest", "tests/test_example.py"]


def test_no_coverage_requires_explicit_diagnostic_selection():
    arguments = pytest_arguments(["tests/test_example.py"], True)
    assert arguments[1:] == ["-m", "pytest", "-o", "addopts=", "--no-cov", "tests/test_example.py"]


def test_implicit_whole_repository_run_is_rejected():
    with pytest.raises(ValueError, match="Explicit test paths"):
        pytest_arguments([], False)
