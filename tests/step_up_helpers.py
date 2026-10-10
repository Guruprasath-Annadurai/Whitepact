# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real TOTP for step-up tests.

Step-up used to accept ``"123456"`` from any principal. It now checks a one-time code against an enrolled
factor and refuses a reused time step. Tests therefore enrol a real secret and generate real codes.
``TotpTimeline`` moves the verifier's clock forward 30 s per code, so each code belongs to a fresh time
step and tests that perform several step-ups never collide with the replay guard.
"""

from __future__ import annotations

import time
from typing import Any

import pyotp
from sqlalchemy import insert, select, update

from responsibleai.auth import mfa
from responsibleai.db.engine import human_totp_factors, org_api_keys, organizations


class TotpTimeline:
    def __init__(self, monkeypatch: Any) -> None:
        self.now = time.time()
        import responsibleai.iam.step_up as step_up

        monkeypatch.setattr(step_up, "_epoch_now", lambda: self.now)

    def code(self, secret: str) -> str:
        """A valid code for a time step later than any this timeline produced before."""
        self.now += 30
        return pyotp.TOTP(secret).at(self.now)

    def stale_code(self, secret: str) -> str:
        """A code that was valid two full windows ago (outside the accepted drift)."""
        return pyotp.TOTP(secret).at(self.now - 120)


async def enroll_api_key_mfa(engine: Any, org_id: str, principal_id: str) -> str:
    """Create (if needed) the organization and an API-key principal with an ACTIVE TOTP secret."""
    secret = mfa.generate_secret()
    async with engine.raw.begin() as conn:
        if (
            await conn.execute(select(organizations.c.id).where(organizations.c.id == org_id))
        ).first() is None:
            await conn.execute(
                insert(organizations).values(
                    id=org_id,
                    name=f"{org_id} Corp",
                    slug=org_id.replace("_", "-"),
                    monthly_budget_usd=10000.0,
                    created_at="2026-09-12T00:00:00Z",
                    plan="ENTERPRISE",
                )
            )
        existing = (
            await conn.execute(select(org_api_keys.c.id).where(org_api_keys.c.id == principal_id))
        ).first()
        if existing is None:
            await conn.execute(
                insert(org_api_keys).values(
                    id=principal_id,
                    org_id=org_id,
                    name=principal_id,
                    role="ADMIN",
                    key_hash=f"hash-{principal_id}",
                    created_at="2026-09-12T00:00:00Z",
                    revoked=0,
                    mfa_enrolled=1,
                    mfa_secret=secret,
                )
            )
        else:
            await conn.execute(
                update(org_api_keys)
                .where(org_api_keys.c.id == principal_id)
                .values(mfa_enrolled=1, mfa_secret=secret, mfa_last_timestep=None)
            )
    return secret


async def enroll_human_mfa(engine: Any, user_id: str) -> str:
    """An ACTIVE human TOTP factor for an existing web user."""
    secret = mfa.generate_secret()
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(human_totp_factors).values(
                user_id=user_id,
                secret_encrypted=secret,
                pending_secret_encrypted=None,
                status="ACTIVE",
                created_at="2026-09-12T00:00:00Z",
                confirmed_at="2026-09-12T00:00:00Z",
            )
        )
    return secret


TIMELINE: TotpTimeline | None = None


async def valid_totp_code(engine: Any, org_id: str, principal_id: str) -> str:
    """Enrol (or re-enrol) the API-key principal and return a fresh, unused, valid code."""
    assert TIMELINE is not None, "the autouse totp fixture is not active"
    async with engine.raw.connect() as conn:
        row = (
            await conn.execute(
                select(org_api_keys.c.mfa_secret, org_api_keys.c.mfa_enrolled).where(
                    org_api_keys.c.id == principal_id
                )
            )
        ).first()
    if row is not None and row[1] and row[0]:
        secret = row[0]  # already enrolled: reuse, so earlier codes for this principal stay valid
    else:
        secret = await enroll_api_key_mfa(engine, org_id, principal_id)
    return TIMELINE.code(secret)


async def valid_human_totp_code(engine: Any, user_id: str) -> str:
    """Return a fresh valid code for a web user, enrolling an ACTIVE human TOTP factor if absent."""
    assert TIMELINE is not None, "the autouse totp fixture is not active"
    async with engine.raw.connect() as conn:
        row = (
            await conn.execute(
                select(human_totp_factors.c.secret_encrypted).where(
                    human_totp_factors.c.user_id == user_id,
                    human_totp_factors.c.status == "ACTIVE",
                )
            )
        ).first()
    secret = row[0] if row else await enroll_human_mfa(engine, user_id)
    return TIMELINE.code(secret)
