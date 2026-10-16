# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Defensive configuration invariants; no credentials, requests or authority seeds."""

import pytest

import responsibleai.dashboard.app as dashboard
from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.enterprise.security import router


@pytest.fixture
def production_configuration(monkeypatch):
    for key in ("WHITEPACT_WEBAUTHN_ORIGIN", "WHITEPACT_WEBAUTHN_RP_ID", "WP_ORIGIN", "WP_RP_ID"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(dashboard.settings, "environment", "production")
    monkeypatch.setattr(dashboard.settings, "webauthn_rp_id", "app.example.com")
    monkeypatch.setattr(router, "get_enterprise_engine", lambda: object())


def test_production_accepts_explicit_https_origin(production_configuration, monkeypatch):
    monkeypatch.setattr(dashboard.settings, "webauthn_origin", "https://app.example.com")
    service = router._svc()
    assert service.origin == "https://app.example.com"


def test_production_rejects_explicit_plain_http_origin(production_configuration, monkeypatch):
    monkeypatch.setattr(dashboard.settings, "webauthn_origin", "http://app.example.com")
    with pytest.raises((ValueError, RuntimeError, EnterpriseError)):
        router._svc()


def test_production_rejects_missing_origin(production_configuration, monkeypatch):
    monkeypatch.setattr(dashboard.settings, "webauthn_origin", "")
    with pytest.raises((ValueError, RuntimeError, EnterpriseError)):
        router._svc()
