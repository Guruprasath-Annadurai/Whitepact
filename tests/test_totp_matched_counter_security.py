# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M3-P1-TOTP-REPLAY-01: matched-counter consumption and boundary replay tests."""

from __future__ import annotations

import asyncio
import datetime
from unittest.mock import AsyncMock, patch

import pyotp
import pytest
from sqlalchemy import select

from responsibleai.auth import mfa
from responsibleai.db.engine import create_engine, human_totp_factors
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.errors import CHALLENGE_REPLAY, EnterpriseError
from responsibleai.enterprise.security.service import IdentitySecurityService

DEFECT_ID = "M3-P1-TOTP-REPLAY-01"


@pytest.fixture
async def engine():
    db = create_engine(":memory:")
    await db.init()
    yield db
    await db.close()


async def _user(engine) -> str:
    web = WebIdentityRepository(engine)
    user_id, token = await web.register("Human", "totp-security@example.com", "correct-horse-battery-staple-9")
    assert await web.verify_email(token)
    return user_id


async def _svc(engine) -> IdentitySecurityService:
    return IdentitySecurityService(engine, rp_id="localhost", origin="http://localhost")


async def _pending_secret(engine, user_id: str) -> str:
    async with engine.raw.connect() as conn:
        return (
            await conn.execute(
                select(human_totp_factors.c.pending_secret_encrypted).where(
                    human_totp_factors.c.user_id == user_id
                )
            )
        ).scalar()


def _code_at(secret: str, unix_ts: float) -> str:
    return pyotp.TOTP(secret).at(datetime.datetime.fromtimestamp(unix_ts))


async def _verify_attempt(
    svc: IdentitySecurityService,
    user_id: str,
    code: str,
    unix_ts: float,
) -> str:
    try:
        with patch("time.time", return_value=unix_ts):
            await svc.verify_totp(user_id, code)
        return "ok"
    except EnterpriseError as exc:
        return exc.code


class TestVerifyCodeWithCounter:
    def test_returns_matched_counter_not_wall_clock_only(self) -> None:
        secret = mfa.generate_secret()
        base_n = 5_700_000
        ts_n_end = base_n * 30 + 29
        code_n = _code_at(secret, ts_n_end)
        ts_n1 = (base_n + 1) * 30 + 1
        matched = mfa.verify_code_with_counter(secret, code_n, now=ts_n1)
        assert matched == base_n

    def test_stale_counter_after_newer_consumed_is_rejected_by_service(self, engine) -> None:
        pytest.skip("covered in async boundary tests")


@pytest.mark.asyncio
async def test_m3_p1_reproduce_cross_window_verify_replay(engine) -> None:
    """Black-box: code consumed in N must not verify again in N+1 via skew window."""
    user_id = await _user(engine)
    svc = await _svc(engine)
    secret = mfa.generate_secret()
    await svc.start_totp(user_id)
    from sqlalchemy import update

    async with engine.raw.begin() as conn:
        await conn.execute(
            update(human_totp_factors)
            .where(human_totp_factors.c.user_id == user_id)
            .values(pending_secret_encrypted=secret)
        )

    counter_n = 5_700_100
    t_confirm = counter_n * 30 + 29
    code = _code_at(secret, t_confirm)

    with patch("time.time", return_value=t_confirm):
        await svc.confirm_totp(user_id, code)

    async with engine.raw.connect() as conn:
        last = (
            await conn.execute(
                select(human_totp_factors.c.last_timestep).where(human_totp_factors.c.user_id == user_id)
            )
        ).scalar()
    assert last == counter_n

    t_verify = (counter_n + 1) * 30 + 1
    with patch("time.time", return_value=t_verify):
        with pytest.raises(EnterpriseError) as exc:
            await svc.verify_totp(user_id, code)
    assert exc.value.code == CHALLENGE_REPLAY


@pytest.mark.asyncio
async def test_confirm_then_verify_replay_same_and_next_window(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    await svc.start_totp(user_id)
    secret = await _pending_secret(engine, user_id)
    counter_n = 5_700_200
    t_n = counter_n * 30 + 15
    code = _code_at(secret, t_n)
    with patch("time.time", return_value=t_n):
        await svc.confirm_totp(user_id, code)
        with pytest.raises(EnterpriseError) as same:
            await svc.verify_totp(user_id, code)
        assert same.value.code == CHALLENGE_REPLAY
    t_n1 = (counter_n + 1) * 30 + 2
    with patch("time.time", return_value=t_n1):
        with pytest.raises(EnterpriseError) as nxt:
            await svc.verify_totp(user_id, code)
        assert nxt.value.code == CHALLENGE_REPLAY


@pytest.mark.asyncio
async def test_verify_verify_replay_and_monotonic_skew(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    await svc.start_totp(user_id)
    secret = await _pending_secret(engine, user_id)
    counter_n = 5_700_300
    t_n = counter_n * 30 + 28
    code_n = _code_at(secret, t_n)
    with patch("time.time", return_value=t_n):
        await svc.confirm_totp(user_id, code_n)

    code_n1 = _code_at(secret, (counter_n + 1) * 30 + 5)
    t_n1 = (counter_n + 1) * 30 + 5
    with patch("time.time", return_value=t_n1):
        await svc.verify_totp(user_id, code_n1)

    with patch("time.time", return_value=t_n1 + 1):
        with pytest.raises(EnterpriseError) as replay:
            await svc.verify_totp(user_id, code_n1)
        assert replay.value.code == CHALLENGE_REPLAY

    with patch("time.time", return_value=t_n1 + 2):
        with pytest.raises(EnterpriseError) as stale:
            await svc.verify_totp(user_id, code_n)
        assert stale.value.code == CHALLENGE_REPLAY


@pytest.mark.asyncio
async def test_previous_window_code_once_then_replay(engine) -> None:
    """After confirm at N-1, a code for counter N (skew) succeeds once then replays."""
    user_id = await _user(engine)
    svc = await _svc(engine)
    await svc.start_totp(user_id)
    secret = await _pending_secret(engine, user_id)
    counter_n = 5_700_400
    t_enroll = (counter_n - 1) * 30 + 20
    with patch("time.time", return_value=t_enroll):
        await svc.confirm_totp(user_id, _code_at(secret, t_enroll))

    t_verify = counter_n * 30 + 5
    code_n = _code_at(secret, t_verify)
    with patch("time.time", return_value=t_verify):
        await svc.verify_totp(user_id, code_n)
        with pytest.raises(EnterpriseError) as replay:
            await svc.verify_totp(user_id, code_n)
        assert replay.value.code == CHALLENGE_REPLAY


@pytest.mark.asyncio
async def test_outside_valid_window_rejected(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    await svc.start_totp(user_id)
    secret = await _pending_secret(engine, user_id)
    counter_n = 5_700_500
    with patch("time.time", return_value=counter_n * 30):
        await svc.confirm_totp(user_id, _code_at(secret, counter_n * 30))

    code_far = _code_at(secret, (counter_n - 3) * 30)
    with patch("time.time", return_value=counter_n * 30 + 5):
        with pytest.raises(EnterpriseError):
            await svc.verify_totp(user_id, code_far)


@pytest.mark.asyncio
async def test_concurrent_verify_single_success(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    await svc.start_totp(user_id)
    secret = await _pending_secret(engine, user_id)
    counter_n = 5_700_600
    t = counter_n * 30 + 10
    with patch("time.time", return_value=t):
        await svc.confirm_totp(user_id, _code_at(secret, t))

    t_verify = (counter_n + 1) * 30 + 8
    code = _code_at(secret, t_verify)
    attempts = 30
    svc.limiter.check = AsyncMock()

    results = await asyncio.gather(
        *[_verify_attempt(svc, user_id, code, t_verify) for _ in range(attempts)]
    )
    assert results.count("ok") == 1
    assert sum(1 for r in results if r != "ok") == attempts - 1
    assert CHALLENGE_REPLAY in results
    assert svc.limiter.check.await_count >= attempts


try:
    from tests.pg_test_url import isolated_pg_url
except ImportError:
    isolated_pg_url = None  # type: ignore[misc, assignment]


@pytest.mark.asyncio
@pytest.mark.skipif(isolated_pg_url is None, reason="pg test helpers unavailable")
async def test_concurrent_verify_postgres() -> None:
    async for pg_url in isolated_pg_url("wp_totp_replay"):
        engine = create_engine(pg_url)
        await engine.init()
        try:
            user_id = await _user(engine)
            svc = await _svc(engine)
            await svc.start_totp(user_id)
            secret = await _pending_secret(engine, user_id)
            counter_n = 5_700_700
            t = counter_n * 30 + 12
            with patch("time.time", return_value=t):
                await svc.confirm_totp(user_id, _code_at(secret, t))
            t_verify = (counter_n + 1) * 30 + 8
            code = _code_at(secret, t_verify)
            svc.limiter.check = AsyncMock()

            results = await asyncio.gather(
                *[_verify_attempt(svc, user_id, code, t_verify) for _ in range(50)]
            )
            assert results.count("ok") == 1
            assert sum(1 for r in results if r != "ok") == 49
            assert CHALLENGE_REPLAY in results
        finally:
            await engine.close()
        break
