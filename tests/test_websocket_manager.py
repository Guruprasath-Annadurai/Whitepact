# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for dashboard.websocket_manager.ConnectionManager -- previously
entirely untested. Uses lightweight fake WebSocket objects (async accept/
send_json) instead of a real FastAPI WebSocket, since the manager only ever
calls those two methods on the object it's given."""

from __future__ import annotations

import asyncio

import pytest

from responsibleai.dashboard.websocket_manager import ConnectionManager


class FakeWebSocket:
    def __init__(self, fail_send: bool = False):
        self.accepted = False
        self.sent: list[dict] = []
        self._fail_send = fail_send

    async def accept(self):
        self.accepted = True

    async def send_json(self, message):
        if self._fail_send:
            raise RuntimeError("connection closed")
        self.sent.append(message)


class TestConnect:
    async def test_accepts_and_registers_connection(self):
        mgr = ConnectionManager()
        ws = FakeWebSocket()
        await mgr.connect(ws, "key1")
        assert ws.accepted is True
        assert mgr.connection_count == 1
        assert mgr.tenant_count == 1

    async def test_multiple_sockets_same_key(self):
        mgr = ConnectionManager()
        ws1, ws2 = FakeWebSocket(), FakeWebSocket()
        await mgr.connect(ws1, "key1")
        await mgr.connect(ws2, "key1")
        assert mgr.connection_count == 2
        assert mgr.tenant_count == 1


class TestDisconnect:
    async def test_removes_socket_and_keeps_other_sockets_for_key(self):
        mgr = ConnectionManager()
        ws1, ws2 = FakeWebSocket(), FakeWebSocket()
        await mgr.connect(ws1, "key1")
        await mgr.connect(ws2, "key1")
        mgr.disconnect(ws1, "key1")
        assert mgr.connection_count == 1
        assert mgr.tenant_count == 1

    async def test_removes_key_entirely_when_last_socket_disconnects(self):
        mgr = ConnectionManager()
        ws = FakeWebSocket()
        await mgr.connect(ws, "key1")
        mgr.disconnect(ws, "key1")
        assert mgr.connection_count == 0
        assert mgr.tenant_count == 0

    def test_disconnect_unknown_key_is_a_noop(self):
        mgr = ConnectionManager()
        ws = FakeWebSocket()
        mgr.disconnect(ws, "nonexistent")  # must not raise
        assert mgr.connection_count == 0

    async def test_disconnect_socket_not_in_bucket_is_a_noop(self):
        mgr = ConnectionManager()
        ws1, ws2 = FakeWebSocket(), FakeWebSocket()
        await mgr.connect(ws1, "key1")
        mgr.disconnect(ws2, "key1")  # ws2 was never connected under key1
        assert mgr.connection_count == 1


class TestBroadcast:
    async def test_broadcast_to_specific_api_key(self):
        mgr = ConnectionManager()
        ws1, ws2 = FakeWebSocket(), FakeWebSocket()
        await mgr.connect(ws1, "key1")
        await mgr.connect(ws2, "key2")
        sent = await mgr.broadcast({"type": "x"}, api_key="key1")
        assert sent == 1
        assert ws1.sent == [{"type": "x"}]
        assert ws2.sent == []

    async def test_broadcast_to_all_when_no_api_key(self):
        mgr = ConnectionManager()
        ws1, ws2 = FakeWebSocket(), FakeWebSocket()
        await mgr.connect(ws1, "key1")
        await mgr.connect(ws2, "key2")
        sent = await mgr.broadcast({"type": "x"})
        assert sent == 2

    async def test_broadcast_to_unknown_key_reaches_nobody(self):
        mgr = ConnectionManager()
        sent = await mgr.broadcast({"type": "x"}, api_key="nonexistent")
        assert sent == 0

    async def test_broadcast_cleans_up_dead_connections(self):
        mgr = ConnectionManager()
        alive, dead = FakeWebSocket(), FakeWebSocket(fail_send=True)
        await mgr.connect(alive, "key1")
        await mgr.connect(dead, "key1")
        sent = await mgr.broadcast({"type": "x"}, api_key="key1")
        assert sent == 1
        assert mgr.connection_count == 1

    async def test_broadcast_with_no_connections_at_all(self):
        mgr = ConnectionManager()
        sent = await mgr.broadcast({"type": "x"})
        assert sent == 0


class TestFindKey:
    async def test_finds_key_for_known_socket(self):
        mgr = ConnectionManager()
        ws = FakeWebSocket()
        await mgr.connect(ws, "key1")
        assert mgr._find_key(ws) == "key1"

    def test_returns_none_for_unknown_socket(self):
        mgr = ConnectionManager()
        assert mgr._find_key(FakeWebSocket()) is None


class TestStartStop:
    async def test_start_creates_heartbeat_task(self):
        mgr = ConnectionManager()
        mgr.start()
        try:
            assert mgr._heartbeat_task is not None
            assert not mgr._heartbeat_task.done()
        finally:
            mgr.stop()

    async def test_start_is_idempotent_while_running(self):
        mgr = ConnectionManager()
        mgr.start()
        first_task = mgr._heartbeat_task
        mgr.start()
        try:
            assert mgr._heartbeat_task is first_task
        finally:
            mgr.stop()

    async def test_start_creates_new_task_after_previous_one_finished(self):
        mgr = ConnectionManager()
        mgr._heartbeat_task = asyncio.create_task(asyncio.sleep(0))
        await mgr._heartbeat_task
        assert mgr._heartbeat_task.done()
        mgr.start()
        try:
            assert not mgr._heartbeat_task.done()
        finally:
            mgr.stop()

    def test_stop_without_start_is_a_noop(self):
        mgr = ConnectionManager()
        mgr.stop()  # must not raise

    async def test_stop_cancels_running_task(self):
        mgr = ConnectionManager()
        mgr.start()
        task = mgr._heartbeat_task
        mgr.stop()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_stop_when_task_already_done_is_a_noop(self):
        mgr = ConnectionManager()
        mgr._heartbeat_task = asyncio.create_task(asyncio.sleep(0))
        await mgr._heartbeat_task
        mgr.stop()  # must not raise, must not try to cancel a finished task


class TestHeartbeatLoop:
    async def test_heartbeat_loop_broadcasts_ping(self, monkeypatch):
        mgr = ConnectionManager()

        async def _fast_sleep(_seconds):
            return None

        broadcasts = []

        async def _fake_broadcast(message, api_key=None):
            broadcasts.append(message)
            raise asyncio.CancelledError()

        monkeypatch.setattr("responsibleai.dashboard.websocket_manager.asyncio.sleep", _fast_sleep)
        monkeypatch.setattr(mgr, "broadcast", _fake_broadcast)

        with pytest.raises(asyncio.CancelledError):
            await mgr._heartbeat_loop()

        assert broadcasts == [{"type": "ping", "connections": 0}]
