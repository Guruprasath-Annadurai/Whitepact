# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Atomic tenant capacity reservation (infrastructure, never authority).

Reserve and release MUST be a single Redis EVAL of one Lua script so a
crash cannot create a reservation without a counter increment, or a
counter decrement without removing the reservation.

Repeated reserve/release are idempotent.

Reservation TTL is renewed by heartbeat and MUST be >= the worker lease
TTL so Redis expiry cannot drop a still-leased execution.

Redis is not execution authority. Losing Redis loses capacity accounting
only; PostgreSQL authorization still decides whether work may proceed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

RESERVE_LUA = """
-- KEYS[1] reservation key  wp:cap:res:{execution_id}
-- KEYS[2] tenant count key wp:cap:tenant:{org_id}
-- ARGV[1] ttl seconds
-- ARGV[2] tenant capacity limit (0 = unlimited)
-- ARGV[3] reservation marker
local ttl = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
if redis.call('EXISTS', KEYS[1]) == 1 then
  redis.call('EXPIRE', KEYS[1], ttl)
  local count = tonumber(redis.call('GET', KEYS[2]) or '0')
  return {1, count, 0}
end
local count = tonumber(redis.call('GET', KEYS[2]) or '0')
if limit > 0 and count >= limit then
  return {0, count, 0}
end
redis.call('SET', KEYS[1], ARGV[3], 'EX', ttl)
count = redis.call('INCR', KEYS[2])
return {1, count, 1}
"""

RELEASE_LUA = """
-- KEYS[1] reservation key
-- KEYS[2] tenant count key
if redis.call('EXISTS', KEYS[1]) == 0 then
  local count = tonumber(redis.call('GET', KEYS[2]) or '0')
  return {1, count, 0}
end
redis.call('DEL', KEYS[1])
local count = tonumber(redis.call('GET', KEYS[2]) or '0')
if count > 0 then
  count = redis.call('DECR', KEYS[2])
else
  redis.call('SET', KEYS[2], '0')
  count = 0
end
if count < 0 then
  redis.call('SET', KEYS[2], '0')
  count = 0
end
return {1, count, 1}
"""

HEARTBEAT_LUA = """
-- KEYS[1] reservation key
-- ARGV[1] ttl seconds
if redis.call('EXISTS', KEYS[1]) == 0 then
  return 0
end
redis.call('EXPIRE', KEYS[1], ARGV[1])
return 1
"""


class RedisEval(Protocol):
    def eval(self, script: str, numkeys: int, *keys_and_args: Any) -> Any: ...


@dataclass(frozen=True)
class CapacityResult:
    ok: bool
    tenant_count: int
    mutated: bool


class AtomicCapacityReservation:
    """EVAL-backed capacity accounting. Does not authorize execution."""

    def __init__(self, redis: RedisEval, *, key_prefix: str = "wp:cap") -> None:
        self._redis = redis
        self._prefix = key_prefix

    def _reservation_key(self, execution_id: str) -> str:
        return f"{self._prefix}:res:{execution_id}"

    def _tenant_key(self, organization_id: str) -> str:
        return f"{self._prefix}:tenant:{organization_id}"

    def reserve(
        self,
        *,
        execution_id: str,
        organization_id: str,
        ttl_seconds: int,
        tenant_limit: int = 0,
    ) -> CapacityResult:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        raw = self._redis.eval(
            RESERVE_LUA,
            2,
            self._reservation_key(execution_id),
            self._tenant_key(organization_id),
            str(ttl_seconds),
            str(tenant_limit),
            execution_id,
        )
        return CapacityResult(ok=bool(raw[0]), tenant_count=int(raw[1]), mutated=bool(raw[2]))

    def release(self, *, execution_id: str, organization_id: str) -> CapacityResult:
        raw = self._redis.eval(
            RELEASE_LUA,
            2,
            self._reservation_key(execution_id),
            self._tenant_key(organization_id),
        )
        return CapacityResult(ok=bool(raw[0]), tenant_count=int(raw[1]), mutated=bool(raw[2]))

    def heartbeat(self, *, execution_id: str, ttl_seconds: int) -> bool:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        raw = self._redis.eval(
            HEARTBEAT_LUA,
            1,
            self._reservation_key(execution_id),
            str(ttl_seconds),
        )
        return bool(raw)


class InMemoryRedisEval:
    """Deterministic Lua-equivalent store for unit tests without Redis."""

    def __init__(self) -> None:
        self._kv: dict[str, str] = {}

    def eval(self, script: str, numkeys: int, *keys_and_args: Any) -> Any:
        args = list(keys_and_args)
        if script is RESERVE_LUA:
            res_key, tenant_key = args[0], args[1]
            ttl, limit, marker = int(args[2]), int(args[3]), str(args[4])
            _ = ttl
            if res_key in self._kv:
                return [1, int(self._kv.get(tenant_key, "0")), 0]
            count = int(self._kv.get(tenant_key, "0"))
            if limit > 0 and count >= limit:
                return [0, count, 0]
            self._kv[res_key] = marker
            count += 1
            self._kv[tenant_key] = str(count)
            return [1, count, 1]
        if script is RELEASE_LUA:
            res_key, tenant_key = args[0], args[1]
            if res_key not in self._kv:
                return [1, int(self._kv.get(tenant_key, "0")), 0]
            del self._kv[res_key]
            count = int(self._kv.get(tenant_key, "0"))
            count = max(count - 1, 0)
            self._kv[tenant_key] = str(count)
            return [1, count, 1]
        if script is HEARTBEAT_LUA:
            res_key = args[0]
            return 1 if res_key in self._kv else 0
        raise ValueError("unknown lua script")
