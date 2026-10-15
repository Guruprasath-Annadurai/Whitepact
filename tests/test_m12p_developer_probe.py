# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Actual SDK consumer contract, using labelled local transport fixtures only."""

import asyncio
import importlib.util
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).parents[1]


@pytest.fixture
def example(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "sdk/python"))
    spec = importlib.util.spec_from_file_location(
        "m12p_probe", ROOT / "examples/developer/m12p_governance_probe.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "status,expected",
    [
        (200, "READ_RESPONSE_RECEIVED"),
        (401, "AUTHENTICATION_REQUIRED"),
        (403, "ACCESS_DENIED"),
        (503, "READ_REQUEST_FAILED"),
    ],
)
def test_real_sdk_only_reads_bounded_evidence(example, monkeypatch, status, expected):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.method == "GET"
        assert request.url.path == "/api/governance/evidence"
        assert dict(request.url.params) == {"limit": "1"}
        assert request.headers["Authorization"] == "Bearer synthetic-private"
        assert not request.content
        return httpx.Response(status, json={"items": [], "private": "do-not-display"})

    actual = example.GovernanceRuntimeClient
    monkeypatch.setattr(
        example,
        "GovernanceRuntimeClient",
        lambda **kwargs: actual(**kwargs, transport=httpx.MockTransport(handler)),
    )
    result = asyncio.run(
        example.probe(
            {
                "WHITEPACT_DEVELOPER_URL": "http://127.0.0.1:8765",
                "WHITEPACT_DEVELOPER_API_KEY": "synthetic-private",
            }
        )
    )
    assert result == expected
    assert len(calls) == 1
    assert "private" not in result


def test_transport_timeout_is_not_retried(example, monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("synthetic-private", request=request)

    actual = example.GovernanceRuntimeClient
    monkeypatch.setattr(
        example,
        "GovernanceRuntimeClient",
        lambda **kwargs: actual(**kwargs, transport=httpx.MockTransport(handler)),
    )
    assert (
        asyncio.run(
            example.probe(
                {
                    "WHITEPACT_DEVELOPER_URL": "http://127.0.0.1:8765",
                    "WHITEPACT_DEVELOPER_API_KEY": "synthetic-private",
                }
            )
        )
        == "READ_UNAVAILABLE"
    )
    assert len(calls) == 1


@pytest.mark.parametrize(
    "url",
    [
        "https://production.example",
        "http://127.0.0.1/?host=evil",
        "http://user:pass@localhost",
        "http://localhost:999999",
        "http://localhost/other",
    ],
)
def test_nonlocal_or_ambiguous_origin_never_dispatches(example, monkeypatch, url):
    monkeypatch.setattr(
        example, "GovernanceRuntimeClient", lambda **kwargs: pytest.fail("must not dispatch")
    )
    assert (
        asyncio.run(
            example.probe(
                {"WHITEPACT_DEVELOPER_URL": url, "WHITEPACT_DEVELOPER_API_KEY": "synthetic-private"}
            )
        )
        == "LOCAL_CONFIGURATION_REQUIRED"
    )
