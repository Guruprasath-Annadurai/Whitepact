# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Read-service validation tests, not authenticated transport qualification."""

from types import SimpleNamespace

import pytest

from responsibleai.mcp.authority_tools import LIST_PENDING_APPROVALS, AuthorityReadService
from responsibleai.rbac.models import OrgContext, Plan, Role


class ReadProbe:
    def __init__(self):
        self.limits = []
        self.reads = []

    async def check(self, key, **kwargs):
        self.limits.append(key)

    async def list_pending(self, org_id, *, limit):
        self.reads.append((org_id, limit))
        return []


def service_and_probe():
    probe = ReadProbe()
    service = AuthorityReadService(SimpleNamespace(approval_repo=probe), probe)
    ctx = OrgContext(key_id="disposable-read", org_id="tenant-a", role=Role.OWNER, plan=Plan.FREE)
    return service, probe, ctx


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cursor",
    ["²", "١", "１", "9" * 5000, "0" * 9, "1\n"],
    ids=["superscript", "arabic", "fullwidth", "integer-limit", "schema-length", "newline"],
)
async def test_invalid_cursor_is_rejected_before_rate_limit_or_repository(cursor):
    service, probe, ctx = service_and_probe()
    result = await service.call(LIST_PENDING_APPROVALS, {"cursor": cursor}, ctx)
    assert result["error"] == "invalid_arguments"
    assert probe.limits == []
    assert probe.reads == []


@pytest.mark.asyncio
@pytest.mark.parametrize("cursor", ["0", "00000000", "150"])
async def test_valid_bounded_ascii_cursor_keeps_tenant_scoped_read(cursor):
    service, probe, ctx = service_and_probe()
    result = await service.call(LIST_PENDING_APPROVALS, {"cursor": cursor}, ctx)
    assert "error" not in result
    assert result["returned"] == 0
    assert probe.reads == [("tenant-a", int(cursor) + 21)]
    assert probe.limits == ["authority_read:tenant-a:whitepact_list_pending_approvals"]
