# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Resume must not invent an identity when the approval recorded none."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from responsibleai.governance.approval import ApprovalRequest
from responsibleai.mcp.governance_integration import _agent_from_approval


def test_resume_refuses_an_approval_with_no_requester() -> None:
    approval = ApprovalRequest(
        action_id="act-1",
        action_type="rai_health",
        target="rai_health",
        reason_codes=[],
        requested_at=datetime.now(UTC),
        organization_id="org-1",
        requested_by="   ",
    )
    with pytest.raises(ValueError, match="requested_by"):
        _agent_from_approval(approval)
