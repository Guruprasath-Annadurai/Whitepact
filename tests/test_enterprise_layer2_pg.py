# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real PostgreSQL races for Layer 2 identity security."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key

from responsibleai.db.engine import create_engine
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.enterprise.security.policy import AuthMethod, SensitiveAction
from responsibleai.enterprise.security.service import IdentitySecurityService
from responsibleai.enterprise.security.webauthn import b64url_decode
from tests.pg_test_url import isolated_pg_url
from tests.webauthn_fakes import registration_blob


@pytest.fixture
async def pg_url() -> AsyncGenerator[str, None]:
    async for url in isolated_pg_url("wp_l2_sec"):
        engine = create_engine(url)
        try:
            await engine.init()
        finally:
            await engine.close()
        yield url


async def _user(engine, email: str) -> str:
    web = WebIdentityRepository(engine)
    user_id, token = await web.register("Human", email, "correct-horse-battery-staple-9")
    assert await web.verify_email(token)
    return user_id


@pytest.mark.asyncio
async def test_postgres_challenge_and_recovery_code_races(pg_url: str) -> None:
    engine = create_engine(pg_url)
    await engine.init()
    try:
        svc = IdentitySecurityService(engine, rp_id="localhost", origin="http://localhost")
        user_id = await _user(engine, "pg-l2@example.com")
        begin = await svc.begin_webauthn(user_id=user_id, session_id="s", ceremony="register")
        challenge = b64url_decode(begin["challenge"])
        key = generate_private_key(SECP256R1())
        cdata, adata, _, _ = registration_blob(
            rp_id="localhost", origin="http://localhost", challenge=challenge, private_key=key
        )
        _, _, session = await svc.issue_session(
            user_id=user_id, methods=(AuthMethod.PASSKEY_UV,), ip_label=None, user_agent=None
        )

        async def finish() -> str | Exception:
            try:
                rec = await svc.finish_passkey_registration(
                    user_id=user_id, session=session, client_data_b64=cdata, authenticator_data_b64=adata
                )
                return rec["id"]
            except Exception as exc:  # noqa: BLE001
                return exc

        first, second = await asyncio.gather(finish(), finish())
        successes = [r for r in (first, second) if isinstance(r, str)]
        failures = [r for r in (first, second) if isinstance(r, Exception)]
        assert len(successes) == 1
        assert len(failures) == 1

        grant = await svc.issue_step_up(session, SensitiveAction.CHANGE_RECOVERY_METHODS, org_id=None)
        codes = await svc.issue_recovery_codes(user_id, session=session, grant=grant)

        async def consume() -> str | Exception:
            try:
                await svc.consume_recovery_code(user_id, codes[0])
                return "ok"
            except Exception as exc:  # noqa: BLE001
                return exc

        c1, c2 = await asyncio.gather(consume(), consume())
        oks = [r for r in (c1, c2) if r == "ok"]
        errs = [r for r in (c1, c2) if r != "ok"]
        assert len(oks) == 1
        assert len(errs) == 1
        assert isinstance(errs[0], EnterpriseError)
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_postgres_account_link_race(pg_url: str) -> None:
    engine = create_engine(pg_url)
    await engine.init()
    try:
        svc = IdentitySecurityService(engine)
        a = await _user(engine, "pg-a@example.com")
        b = await _user(engine, "pg-b@example.com")
        from responsibleai.enterprise.security.oidc import VerifiedIDToken
        import time

        claims = VerifiedIDToken(
            issuer="https://accounts.google.com",
            subject=f"sub-{uuid.uuid4().hex}",
            audience="c",
            email="x@example.com",
            hosted_domain=None,
            tenant_id=None,
            nonce="n",
            expires_at=int(time.time()) + 60,
            raw={},
        )
        _, _, sa = await svc.issue_session(user_id=a, methods=(AuthMethod.PASSKEY_UV,), ip_label=None, user_agent=None)
        _, _, sb = await svc.issue_session(user_id=b, methods=(AuthMethod.PASSKEY_UV,), ip_label=None, user_agent=None)
        ga = await svc.issue_step_up(sa, SensitiveAction.LINK_GOOGLE, org_id=None)
        gb = await svc.issue_step_up(sb, SensitiveAction.LINK_GOOGLE, org_id=None)

        async def link(session, grant):
            try:
                await svc.link_provider(session=session, provider="GOOGLE", claims=claims, grant=grant, account_kind="PERSONAL")
                return "ok"
            except Exception as exc:  # noqa: BLE001
                return exc

        r1, r2 = await asyncio.gather(link(sa, ga), link(sb, gb))
        oks = [r for r in (r1, r2) if r == "ok"]
        assert len(oks) == 1
    finally:
        await engine.close()
