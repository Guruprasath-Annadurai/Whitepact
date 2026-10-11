# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Claude's documented hosted callback is registrable -- exactly, and nothing near it.

Source of the callback (read 2026-10-11): https://claude.com/docs/connectors/building/authentication
"register exactly this redirect URI: https://claude.ai/api/mcp/auth_callback". Claude Code's loopback
redirects are not accepted (see the comment on ``_CLAUDE_HOSTED_CALLBACK``).
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from tests import test_mcp_oauth_authorization_server as _base

oauth_app = _base.oauth_app  # re-exported fixture (a bare import would trip ruff F811)

CLAUDE_CALLBACK = "https://claude.ai/api/mcp/auth_callback"


async def _register(client, redirect_uris):
    return await client.post(
        "/oauth/register",
        json={
            "client_name": "Claude",
            "redirect_uris": redirect_uris,
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        },
    )


async def test_claude_hosted_callback_completes_a_full_pkce_flow(oauth_app) -> None:
    app, _engine, _org, _other, _key_rec, reviewer_key = oauth_app
    async with _base._client(app) as client:
        registered = await _register(client, [CLAUDE_CALLBACK])
        assert registered.status_code == 201, registered.text
        client_id = registered.json()["client_id"]
        assert registered.json()["redirect_uris"] == [CLAUDE_CALLBACK]

        verifier, challenge = _base._pkce()
        start = await client.get(
            "/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": CLAUDE_CALLBACK,
                "scope": f"{_base.REVIEW_SCOPE} offline_access",
                "state": "claude-state",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "resource": _base.RESOURCE,
            },
        )
        assert start.status_code == 200, start.text
        finish = await client.post(
            "/oauth/authorize",
            data={
                "request_id": start.headers["x-whitepact-oauth-request-id"],
                "api_key": reviewer_key,
                "action": "allow",
            },
        )
        assert finish.status_code == 303, finish.text
        location = urlparse(finish.headers["location"])
        assert f"{location.scheme}://{location.netloc}{location.path}" == CLAUDE_CALLBACK
        query = parse_qs(location.query)
        assert query["state"] == ["claude-state"] and query["iss"] == [_base.ISSUER]

        token = await client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "code": query["code"][0],
                "redirect_uri": CLAUDE_CALLBACK,
                "code_verifier": verifier,
                "resource": _base.RESOURCE,
            },
        )
        assert token.status_code == 200, token.text
        assert token.json()["refresh_token"]  # offline_access honoured; rotation covered elsewhere


@pytest.mark.parametrize(
    "uri",
    [
        CLAUDE_CALLBACK + "/",  # trailing slash
        CLAUDE_CALLBACK + "?x=1",  # query smuggling
        CLAUDE_CALLBACK + "#frag",
        "http://claude.ai/api/mcp/auth_callback",  # downgrade
        "https://claude.ai.evil.example/api/mcp/auth_callback",  # suffix host
        "https://evil.example/https://claude.ai/api/mcp/auth_callback",
        "https://claude.ai@evil.example/api/mcp/auth_callback",  # userinfo
        "https://claude.ai:444/api/mcp/auth_callback",  # port
        "https://CLAUDE.AI/api/mcp/auth_callback",  # case is not normalised away
        "https://claude.ai/api/mcp/auth_callback\n",
        "https://claude.com/api/mcp/auth_callback",  # a different registrable name
        "https://www.claude.ai/api/mcp/auth_callback",
        "http://localhost:3118/callback",  # Claude Code loopback: deliberately unsupported
        "http://127.0.0.1:3118/callback",
        "https://claude.ai/*",
    ],
)
async def test_lookalikes_and_loopback_are_refused(oauth_app, uri: str) -> None:
    app, *_ = oauth_app
    async with _base._client(app) as client:
        response = await _register(client, [uri])
    assert response.status_code == 400, (uri, response.text)
    assert response.json()["error"] == "invalid_redirect_uri"


async def test_one_bad_uri_in_a_list_refuses_the_whole_registration(oauth_app) -> None:
    app, *_ = oauth_app
    async with _base._client(app) as client:
        response = await _register(client, [CLAUDE_CALLBACK, "https://evil.example/cb"])
    assert response.status_code == 400


async def test_chatgpt_registration_is_unchanged(oauth_app) -> None:
    app, *_ = oauth_app
    async with _base._client(app) as client:
        assert (await _register(client, [_base.REDIRECT_URI])).status_code == 201
        assert (
            await _register(client, ["https://chatgpt.com/connector/oauth/abc_DEF-123"])
        ).status_code == 201
