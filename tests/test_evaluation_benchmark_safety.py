# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Safety and calculation contracts for the opt-in, local-only benchmark."""

import math
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.evaluation.local_authorization_benchmark import (
    checked_workload,
    percentile,
    summarize,
    validate_local_origin,
)


@pytest.mark.parametrize(
    "origin",
    [
        "https://example.com",
        "http://localhost:8765",
        "http://127.0.0.1.example.com:8765",
        "http://user:secret@127.0.0.1:8765",
        "http://127.0.0.1:8765/path",
        "http://127.0.0.1:8765?url=other",
        "http://127.0.0.1:8765#fragment",
        "http://127.0.0.1",
    ],
)
def test_benchmark_rejects_non_owned_style_targets(origin):
    with pytest.raises(ValueError, match="local benchmark origin"):
        validate_local_origin(origin)


def test_benchmark_accepts_only_explicit_ipv4_loopback_origin():
    validate_local_origin("http://127.0.0.1:19876")


@pytest.mark.parametrize("requests,concurrency", [(0, 1), (201, 4), (24, 0), (100, 101)])
def test_workload_caps(requests, concurrency):
    with pytest.raises(ValueError):
        checked_workload(requests, concurrency)


def test_percentiles_use_documented_nearest_rank_not_interpolated_guess():
    assert percentile(list(range(1, 101)), 50) == 50
    assert percentile(list(range(1, 101)), 95) == 95
    assert percentile(list(range(1, 101)), 99) == 99
    assert percentile([5], 99) == 5
    with pytest.raises(ValueError):
        percentile([], 95)


def test_summary_distinguishes_denials_throttles_and_transport_failures():
    result = summarize([(1.0, "DENIED"), (2.0, "RATE_LIMITED"), (3.0, "TRANSPORT_ERROR")], 2.0)
    assert result["requests_attempted"] == 3
    assert result["requests_per_second"] == 1.5
    assert result["governance_denials"] == 1
    assert result["rate_limited"] == 1
    assert result["errors"] == 1
    assert result["p50_ms"] == 2.0
    assert result["p95_ms"] == 3.0
    assert result["p99_ms"] == 3.0
    assert result["allowed_effects"] == 0
    with pytest.raises(ValueError):
        summarize([(1.0, "DENIED")], 0)


@pytest.mark.parametrize("sample", [math.nan, math.inf, -1])
def test_invalid_latency_not_accepted(sample):
    with pytest.raises(ValueError):
        summarize([(sample, "DENIED")], 1)


def test_missing_explicit_opt_in_does_not_contact_services():
    script = (
        Path(__file__).resolve().parents[1] / "scripts/evaluation/local_authorization_benchmark.py"
    )
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert result.returncode == 2
    assert "--run-local opt-in is required; no service contacted" in result.stderr
    assert not result.stdout


def test_capacity_rejection_is_not_mislabeled_as_governance_throughput():
    result = summarize([(2, "CAPACITY_REJECTED"), (8, "DENIED")], 1)
    assert result["capacity_rejections"] == 1
    assert result["governance_denials"] == 1
    assert result["errors"] == 1
    assert result["allowed_effects"] == 0
