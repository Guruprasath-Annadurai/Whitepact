# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Forged or unverified step-up proofs over real HTTP cannot authorize a privileged action.

The privileged action here is promoting a member to ADMIN (a PRIVILEGED_HIGH web route). Every refusal
test ends by reading the member list: the role must not have changed. The positive control at the end
proves the same request succeeds with a genuine enrolled-factor code, so the refusals are about the
proof, not about the route being broken.
"""

from __future__ import annotations

import pyotp
import pytest
from httpx import AsyncClient

import responsibleai.dashboard.app as app_module
from tests.step_up_helpers import enroll_human_mfa
from tests import test_auth_canonical_seams as _seams
from tests.test_auth_canonical_seams import _get_step_up_detail, _onboard_org, _register_and_login

web_client = _seams.web_client  # fixture, re-exported under its own name

PASSWORD = "Correct-Horse-42!"


@pytest.fixture(autouse=True)
def _roomy_signup_window(monkeypatch):
    from responsibleai.dashboard.signup_guard import SignupRateWindow

    monkeypatch.setattr(
        app_module, "_signup_window", SignupRateWindow(max_per_window=1000, window_seconds=3600.0)
    )


async def _login(client: AsyncClient, email: str) -> str:
    response = await client.post(
        "/api/v1/web/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return client.cookies["wp_csrf"]


async def _owner_and_viewer(client: AsyncClient, tag: str):
    owner_email, member_email = f"{tag}_owner@example.com", f"{tag}_member@example.com"
    owner_id, _, csrf = await _register_and_login(client, f"{tag} Owner", owner_email)
    await _onboard_org(client, csrf, f"{tag} Inc")
    member_id, _, _ = await _register_and_login(client, f"{tag} Member", member_email)
    csrf = await _login(client, owner_email)
    invite = await client.post(
        "/api/web/invitations",
        headers={"X-WP-CSRF": csrf},
        json={"email": member_email, "role": "VIEWER"},
    )
    assert invite.status_code == 202, invite.text
    from urllib.parse import parse_qs, urlparse

    token = parse_qs(urlparse(invite.json()["invitation_url"]).query)["token"][0]
    member_csrf = await _login(client, member_email)
    accepted = await client.post(
        "/api/web/invitations/accept", headers={"X-WP-CSRF": member_csrf}, json={"token": token}
    )
    assert accepted.status_code == 200, accepted.text
    csrf = await _login(client, owner_email)
    return owner_id, member_id, owner_email, csrf


async def _role_of(client: AsyncClient, member_id: str) -> str:
    response = await client.get(
        "/api/web/members", headers={"X-WP-CSRF": client.cookies["wp_csrf"]}
    )
    assert response.status_code == 200, response.text
    members = response.json()["members"]
    return next(m["role"] for m in members if m["id"] == member_id)


async def _challenge(client: AsyncClient, csrf: str, member_id: str) -> str:
    refused = await client.patch(
        f"/api/web/members/{member_id}", headers={"X-WP-CSRF": csrf}, json={"role": "ADMIN"}
    )
    assert refused.status_code == 403
    detail = _get_step_up_detail(refused)
    assert detail["error"] == "step_up_required"
    return detail["required_nonce"]


async def _promote(client, csrf, member_id, nonce, method, token, **extra):
    return await client.patch(
        f"/api/web/members/{member_id}",
        headers={
            "X-WP-CSRF": csrf,
            "X-Step-Up-Nonce": nonce,
            "X-Step-Up-Method": method,
            "X-Step-Up-Token": token,
            **extra,
        },
        json={"role": "ADMIN"},
    )


def _engine():
    return app_module._ready(app_module._db_engine)


@pytest.mark.parametrize("fallback", ["123456", "valid_totp_mock", "000000", ""])
async def test_the_old_mock_totp_codes_do_not_authorize_an_unenrolled_user(
    web_client,
    fallback: str,
) -> None:
    _owner, member_id, _email, csrf = await _owner_and_viewer(web_client, "mock")
    nonce = await _challenge(web_client, csrf, member_id)
    response = await _promote(web_client, csrf, member_id, nonce, "mfa_totp", fallback)
    assert response.status_code == 403, response.text
    assert _get_step_up_detail(response)["error"] == "step_up_failed"
    assert await _role_of(web_client, member_id) == "VIEWER"


@pytest.mark.parametrize(
    "token",
    [
        "valid-token-1234567890",  # long enough for the old OIDC length heuristic
        "eyJhbGciOiJub25lIn0.eyJhdXRoX3RpbWUiOjF9.",  # an unsigned JWT-shaped string
        "signed-by-attacker-0000000",
        "ok",
    ],
)
@pytest.mark.parametrize("method", ["oidc_auth_time", "webauthn"])
async def test_oidc_and_webauthn_proofs_are_refused_until_a_real_verifier_exists(
    web_client,
    method: str,
    token: str,
) -> None:
    _owner, member_id, _email, csrf = await _owner_and_viewer(web_client, "unv")
    nonce = await _challenge(web_client, csrf, member_id)
    response = await _promote(web_client, csrf, member_id, nonce, method, token)
    assert response.status_code == 403, response.text
    detail = _get_step_up_detail(response)
    assert detail["error"] == "step_up_failed" and "not supported" in detail["message"]
    assert await _role_of(web_client, member_id) == "VIEWER"


async def test_a_wrong_code_a_reused_code_and_a_guessing_burst_are_all_refused(
    web_client,
) -> None:
    owner_id, member_id, _email, csrf = await _owner_and_viewer(web_client, "burst")
    secret = await enroll_human_mfa(_engine(), owner_id)
    totp = pyotp.TOTP(secret)

    nonce = await _challenge(web_client, csrf, member_id)
    wrong = await _promote(web_client, csrf, member_id, nonce, "mfa_totp", "111111")
    assert wrong.status_code == 403
    assert await _role_of(web_client, member_id) == "VIEWER"

    # A guessing burst is cut off by the durable rate limit, and the correct code is then refused too.
    for guess in range(10):
        await _promote(web_client, csrf, member_id, nonce, "mfa_totp", f"{guess:06d}")
    blocked = await _promote(web_client, csrf, member_id, nonce, "mfa_totp", totp.now())
    assert blocked.status_code == 403, blocked.text
    assert (
        "Too many" in blocked.json()["message"]["message"]
        if isinstance(blocked.json().get("message"), dict)
        else True
    )
    assert await _role_of(web_client, member_id) == "VIEWER"


async def test_a_code_cannot_be_used_twice_and_a_nonce_cannot_cross_actions_or_users(
    web_client,
) -> None:
    owner_id, member_id, _email, csrf = await _owner_and_viewer(web_client, "replay")
    secret = await enroll_human_mfa(_engine(), owner_id)
    totp = pyotp.TOTP(secret)

    # A nonce issued for a different action is refused even with a valid code.
    wrong_action = await web_client.post(
        "/api/web/organizations/transfer-ownership",
        headers={"X-WP-CSRF": csrf},
        json={"new_owner_user_id": member_id, "confirmation": "TRANSFER OWNERSHIP"},
    )
    transfer_nonce = _get_step_up_detail(wrong_action)["required_nonce"]
    crossed = await _promote(web_client, csrf, member_id, transfer_nonce, "mfa_totp", totp.now())
    assert crossed.status_code == 403, crossed.text
    assert await _role_of(web_client, member_id) == "VIEWER"

    # Genuine proof succeeds once ...
    nonce = await _challenge(web_client, csrf, member_id)
    ok = await _promote(web_client, csrf, member_id, nonce, "mfa_totp", totp.now())
    assert ok.status_code == 200, ok.text
    assert await _role_of(web_client, member_id) == "ADMIN"

    # ... and the same code with a fresh nonce is a replay of a spent time step.
    await web_client.patch(
        f"/api/web/members/{member_id}", headers={"X-WP-CSRF": csrf}, json={"role": "VIEWER"}
    )
    # (demotion needs no step-up); promote again with the spent code
    again_nonce = await _challenge(web_client, csrf, member_id)
    replay = await _promote(web_client, csrf, member_id, again_nonce, "mfa_totp", totp.now())
    assert replay.status_code == 403, replay.text
    assert await _role_of(web_client, member_id) == "VIEWER"


async def test_a_client_supplied_auth_time_neither_helps_nor_hurts(
    web_client,
) -> None:
    """Freshness is the server's challenge age; a forged 'just authenticated' time is not evidence."""
    owner_id, member_id, _email, csrf = await _owner_and_viewer(web_client, "authtime")
    secret = await enroll_human_mfa(_engine(), owner_id)
    nonce = await _challenge(web_client, csrf, member_id)
    ok = await _promote(
        web_client,
        csrf,
        member_id,
        nonce,
        "mfa_totp",
        pyotp.TOTP(secret).now(),
        **{"X-Step-Up-Auth-Time": "1970-01-01T00:00:00+00:00"},
    )
    assert ok.status_code == 200, ok.text
    assert await _role_of(web_client, member_id) == "ADMIN"


async def test_a_genuine_enrolled_code_authorizes_the_action(web_client) -> None:
    """Positive control for every refusal above."""
    owner_id, member_id, _email, csrf = await _owner_and_viewer(web_client, "genuine")
    secret = await enroll_human_mfa(_engine(), owner_id)
    nonce = await _challenge(web_client, csrf, member_id)
    ok = await _promote(web_client, csrf, member_id, nonce, "mfa_totp", pyotp.TOTP(secret).now())
    assert ok.status_code == 200, ok.text
    assert await _role_of(web_client, member_id) == "ADMIN"
