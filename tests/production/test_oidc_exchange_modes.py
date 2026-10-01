# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest

from responsibleai.auth.oidc import OIDCProvider


@pytest.mark.asyncio
async def test_exchange_code_omits_empty_client_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OIDCProvider(
        issuer="https://issuer.example",
        client_id="cid",
        skip_verification=True,
    )
    captured: dict = {}

    class _Resp:
        status_code = 200

        def json(self) -> dict:
            return {"access_token": "t"}

    class _Client:
        async def post(self, _url: str, data: dict) -> _Resp:
            captured["data"] = data
            return _Resp()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr("responsibleai.auth.oidc.httpx.AsyncClient", lambda **kw: _Client())

    async def _discover() -> dict:
        return {"token_endpoint": "https://issuer.example/token"}

    monkeypatch.setattr(provider, "discover", _discover)

    await provider.exchange_code(
        code="c",
        redirect_uri="https://app/cb",
        client_secret="",
        code_verifier="verifier",
    )
    assert "client_secret" not in captured["data"]
    assert captured["data"]["code_verifier"] == "verifier"
