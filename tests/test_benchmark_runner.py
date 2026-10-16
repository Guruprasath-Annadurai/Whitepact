# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Unit tests for the FastStart benchmark runner (FST-R06).

Validates:
1. Portable interpreter discovery.
2. System details extraction.
3. Fail-closed non-zero exit code when any threshold is violated.
4. Correct status classification and error reporting for missing matrix interpreters.
"""

from __future__ import annotations

import argparse
import sys
from unittest.mock import patch

from scripts.benchmark_faststart_targets import (
    benchmark,
    find_interpreters,
    get_system_info,
)


def test_get_system_info_returns_expected_keys() -> None:
    info = get_system_info()
    for key in ("os_name", "os_release", "cpu_arch", "python_runtime", "uv_version"):
        assert key in info
        assert isinstance(info[key], str)


def test_find_interpreters_returns_valid_paths() -> None:
    interpreters = find_interpreters()
    assert len(interpreters) >= 1
    for p in interpreters:
        assert isinstance(p, str)
        assert len(p) > 0


def test_benchmark_returns_failure_when_target_fails() -> None:
    """Proves the runner exits with code 1 when a target fails its threshold."""
    mock_results = {"target_a_cold_uv": 15.0}
    mock_statuses = {"target_a_cold_core": "FAIL", "target_b_warm_core": "PASS"}
    mock_all_passed = False

    with patch(
        "scripts.benchmark_faststart_targets.benchmark_for_python",
        return_value=(mock_results, mock_statuses, mock_all_passed),
    ):
        args = argparse.Namespace(require_matrix=False, python=sys.executable)
        code = benchmark(args)
        assert code == 1, "Benchmark must return non-zero exit code on threshold failure"


def test_benchmark_returns_success_when_all_targets_pass() -> None:
    """Proves the runner exits with code 0 only when all targets pass."""
    mock_results = {"target_a_cold_uv": 8.0}
    mock_statuses = {"target_a_cold_core": "PASS", "target_b_warm_core": "PASS"}
    mock_all_passed = True

    with patch(
        "scripts.benchmark_faststart_targets.benchmark_for_python",
        return_value=(mock_results, mock_statuses, mock_all_passed),
    ):
        args = argparse.Namespace(require_matrix=False, python=sys.executable)
        code = benchmark(args)
        assert code == 0, "Benchmark must return 0 when all targets pass"


def test_benchmark_require_matrix_fails_when_version_missing() -> None:
    """Proves the runner fails cleanly when a required matrix version is missing."""
    args = argparse.Namespace(require_matrix=True, python=None)
    with patch(
        "scripts.benchmark_faststart_targets.find_interpreters",
        return_value=[sys.executable],  # Only 1 version present
    ):
        code = benchmark(args)
        # Should fail because matrix requires both 3.11 and 3.12
        assert code == 1
