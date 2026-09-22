# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Checkpoint 6 transport-boundary adversarial regressions."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import WebSocketDisconnect

import responsibleai.dashboard.app as app_module
from responsibleai.rbac.models import OrgContext, Plan, Role
from responsibleai.webhooks.manager import WebhookManager
from responsibleai.webhooks.models import WebhookConfig, WebhookDelivery, WebhookEvent


async def test_webhook_event_is_delivered_only_to_origin_tenant() -> None:
    manager = WebhookManager()
    org_a = WebhookConfig(
        url="https://a.example.test/hook",
        events=[WebhookEvent.DRIFT_ALERT],
        org_id="org-a",
    )
    org_b = WebhookConfig(
        url="https://b.example.test/hook",
        events=[WebhookEvent.DRIFT_ALERT],
        org_id="org-b",
    )
    manager.register(org_a)
    manager.register(org_b)

    async def deliver(config, event, data, **_kwargs):
        return WebhookDelivery(
            webhook_id=config.id, event=event, payload=data, org_id=config.org_id
        )

    manager._deliver = AsyncMock(side_effect=deliver)  # type: ignore[method-assign]

    deliveries = await manager.fire(
        WebhookEvent.DRIFT_ALERT,
        {"tenant_marker": "org-a-only"},
        org_id="org-a",
    )

    assert [delivery.org_id for delivery in deliveries] == ["org-a"]
    assert manager._deliver.await_count == 1
    assert manager._deliver.await_args.args[0].id == org_a.id


class _DisconnectingWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []
        self.closed: tuple[int, str] | None = None

    async def accept(self) -> None:
        return None

    async def send_json(self, payload) -> None:
        self.sent.append(payload)

    async def receive_text(self) -> str:
        raise WebSocketDisconnect()

    async def close(self, code: int, reason: str) -> None:
        self.closed = (code, reason)


async def test_websocket_normalizes_db_key_to_tenant_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = OrgContext(
        key_id="key-record-a",
        role=Role.ANALYST,
        org_id="org-a",
        plan=Plan.PRO,
    )
    org_repo = AsyncMock()
    org_repo.authenticate.return_value = context
    cost_repo = AsyncMock()
    cost_repo.total_cost.return_value = 12.5
    trust_repo = AsyncMock()
    trust_repo.all_models.return_value = ["model-a"]
    connections = MagicMock()
    connections.connect = AsyncMock()
    connections.connection_count = 1
    socket = _DisconnectingWebSocket()

    monkeypatch.setattr(app_module.settings, "auth_enabled", True)
    monkeypatch.setattr(app_module.settings, "api_keys", [])
    monkeypatch.setattr(app_module, "_org_repo", org_repo)
    monkeypatch.setattr(app_module, "_cost_repo", cost_repo)
    monkeypatch.setattr(app_module, "_trust_repo", trust_repo)
    monkeypatch.setattr(app_module, "_ws_manager", connections)

    await app_module.websocket_dashboard(socket, token="synthetic-org-a-key")  # type: ignore[arg-type]

    org_repo.authenticate.assert_awaited_once_with("synthetic-org-a-key")
    connections.connect.assert_awaited_once_with(socket, "org-a")
    connections.disconnect.assert_called_once_with(socket, "org-a")
    cost_repo.total_cost.assert_awaited_once_with(30, org_id="org-a")
    trust_repo.all_models.assert_awaited_once_with(org_id="org-a")
    assert socket.sent[0]["models"] == ["model-a"]
    assert "org_count" not in socket.sent[0]


async def test_websocket_rejects_legacy_bootstrap_identity_without_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connections = MagicMock()
    connections.connect = AsyncMock()
    connections.connection_count = 0
    socket = _DisconnectingWebSocket()
    monkeypatch.setattr(app_module.settings, "auth_enabled", True)
    monkeypatch.setattr(app_module.settings, "api_keys", ["synthetic-bootstrap-key"])
    monkeypatch.setattr(app_module, "_ws_manager", connections)

    await app_module.websocket_dashboard(socket, token="synthetic-bootstrap-key")  # type: ignore[arg-type]

    assert socket.closed == (4003, "Tenant-scoped credential required")
    connections.connect.assert_not_awaited()


def _calls_named(tree: ast.AST, name: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == name
    ]


def test_production_event_transports_require_explicit_tenant_routing() -> None:
    root = Path(__file__).parents[1]
    app_tree = ast.parse((root / "src/responsibleai/dashboard/app.py").read_text())
    approval_tree = ast.parse((root / "src/responsibleai/db/approval_repository.py").read_text())

    fire_calls = _calls_named(app_tree, "fire") + _calls_named(approval_tree, "fire")
    assert len(fire_calls) == 5
    assert all(any(keyword.arg == "org_id" for keyword in call.keywords) for call in fire_calls)

    dashboard_broadcasts = _calls_named(app_tree, "broadcast")
    assert len(dashboard_broadcasts) == 4
    assert all(
        any(keyword.arg == "api_key" for keyword in call.keywords) for call in dashboard_broadcasts
    )


def test_direct_tool_dispatch_is_confined_to_community_adapter_and_guarded_sink() -> None:
    root = Path(__file__).parents[1]
    production_root = root / "src/responsibleai"
    dispatch_sites: list[tuple[str, str]] = []
    for path in production_root.rglob("*.py"):
        tree = ast.parse(path.read_text())
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent
        for call in ast.walk(tree):
            if not (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "dispatch_tool"
            ):
                continue
            owner = parents.get(call)
            while owner is not None and not isinstance(
                owner, (ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                owner = parents.get(owner)
            dispatch_sites.append((str(path.relative_to(root)), owner.name if owner else ""))

    assert sorted(dispatch_sites) == [
        ("src/responsibleai/governance/execution.py", "execute"),
        ("src/responsibleai/mcp/server.py", "_call_tool"),
    ]
