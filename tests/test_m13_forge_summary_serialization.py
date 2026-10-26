# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Display serialization only; fixture repositories do not qualify authorization."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import responsibleai.dashboard.app as dashboard


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "risk,display", [(None, "Not recorded"), ("LOW", "LOW"), ("FUTURE", "FUTURE")]
)
@pytest.mark.parametrize("policy,policy_display", [(None, "default"), (0, "0"), (3, "3")])
async def test_summary_risk_is_a_literal_display_string(
    monkeypatch, risk, display, policy, policy_display
):
    record = SimpleNamespace(
        evidence_id="ev-1",
        agent_id="agent-1",
        action_type="local.read",
        policy_version=policy,
        risk_tier=risk,
        decision="DENY",
        recorded_at=None,
        evaluated_at=datetime(2026, 10, 16, tzinfo=UTC),
    )
    approvals = SimpleNamespace(list_pending=AsyncMock(return_value=[]))
    evidence = SimpleNamespace(list_for_org=AsyncMock(return_value=[record]))
    monkeypatch.setattr(dashboard, "_approval_repo", approvals)
    monkeypatch.setattr(dashboard, "_evidence_repo", evidence)
    summary = await dashboard.web_dashboard_summary(SimpleNamespace(org_id="org-1"))
    assert summary["recent_governance"][0]["risk"] == display
    assert summary["recent_governance"][0]["policy"] == policy_display
    assert summary["blocked_actions"] == 1
    evidence.list_for_org.assert_awaited_once_with("org-1", limit=50)
    assert record.risk_tier is risk
