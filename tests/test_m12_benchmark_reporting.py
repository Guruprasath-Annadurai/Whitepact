# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
import pytest
from scripts.evaluation.local_authorization_benchmark import (
    checked_workload,
    summarize,
    validate_denial_evidence_window,
)


def test_attempt_rate_never_becomes_completed_execution_throughput():
    result = summarize([(1, "DENIED"), (2, "CAPACITY_REJECTED"), (3, "RATE_LIMITED")], 2)
    assert result["attempted_requests_per_second"] == 1.5
    assert result["governance_denials_per_second"] == 0.5
    assert result["successful_execution_throughput_qualified"] is False


@pytest.mark.parametrize("requests,concurrency", [(True, 4), (24, False), (1.5, 4), (24, 1.5)])
def test_workload_rejects_noninteger_counts(requests, concurrency):
    with pytest.raises(ValueError):
        checked_workload(requests, concurrency)


def test_bounded_200_row_api_window_does_not_hide_missing_durable_warmup():
    records = [{"organization_id": "owned", "decision": "DENY"}] * 200
    validate_denial_evidence_window(records, 200, 201, "owned")
    with pytest.raises(RuntimeError):
        validate_denial_evidence_window(records, 200, 200, "owned")


def test_another_tenant_or_wrong_decision_never_proves_durable_denial():
    for record in (
        {"organization_id": "other", "decision": "DENY"},
        {"organization_id": "owned", "decision": "ALLOW"},
        None,
    ):
        with pytest.raises(RuntimeError):
            validate_denial_evidence_window([record], 0, 1, "owned")
