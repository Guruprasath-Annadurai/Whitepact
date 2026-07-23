"""Tests for responsibleai.dashboard.config.Settings — env var parsing.

Regression coverage for a real startup-crashing bug found while building
MFA support: api_keys/allowed_origins/oidc_scopes are list[str] fields with
custom comma-splitting validators, but pydantic-settings tries to
JSON-decode the raw env var *before* handing it to those validators. The
documented format (RAI_API_KEYS=key1,key2 — see .env.example,
DEPLOY_RUNBOOK.md) isn't valid JSON, so every self-hosted deployment that
followed the docs literally would crash at import time with a
SettingsError, never reaching a running server. Fixed via NoDecode.
"""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture()
def fresh_settings_module(monkeypatch: pytest.MonkeyPatch):
    """Import a fresh copy of the config module so env vars set mid-test
    are actually picked up (Settings() re-reads os.environ on construction,
    but the module-level get_settings() cache would otherwise mask this)."""
    import responsibleai.dashboard.config as config_module
    importlib.reload(config_module)
    return config_module


class TestApiKeysEnvParsing:
    def test_comma_separated_string_does_not_crash(self, monkeypatch, fresh_settings_module) -> None:
        monkeypatch.setenv("RAI_API_KEYS", "key1,key2,key3")
        settings = fresh_settings_module.Settings()
        assert settings.api_keys == ["key1", "key2", "key3"]

    def test_single_key_no_comma(self, monkeypatch, fresh_settings_module) -> None:
        monkeypatch.setenv("RAI_API_KEYS", "solo-key")
        settings = fresh_settings_module.Settings()
        assert settings.api_keys == ["solo-key"]

    def test_unset_defaults_to_empty_list(self, monkeypatch, fresh_settings_module) -> None:
        monkeypatch.delenv("RAI_API_KEYS", raising=False)
        settings = fresh_settings_module.Settings()
        assert settings.api_keys == []

    def test_whitespace_around_keys_is_stripped(self, monkeypatch, fresh_settings_module) -> None:
        monkeypatch.setenv("RAI_API_KEYS", " key1 , key2 ")
        settings = fresh_settings_module.Settings()
        assert settings.api_keys == ["key1", "key2"]


class TestAllowedOriginsEnvParsing:
    def test_comma_separated_string_does_not_crash(self, monkeypatch, fresh_settings_module) -> None:
        monkeypatch.setenv("RAI_ALLOWED_ORIGINS", "https://a.example.com,https://b.example.com")
        settings = fresh_settings_module.Settings()
        assert settings.allowed_origins == ["https://a.example.com", "https://b.example.com"]

    def test_unset_uses_documented_default(self, monkeypatch, fresh_settings_module) -> None:
        monkeypatch.delenv("RAI_ALLOWED_ORIGINS", raising=False)
        settings = fresh_settings_module.Settings()
        assert settings.allowed_origins == [
            "http://localhost:8765",
            "http://127.0.0.1:8765",
        ]


class TestOidcScopesEnvParsing:
    def test_comma_separated_string_does_not_crash(self, monkeypatch, fresh_settings_module) -> None:
        monkeypatch.setenv("RAI_OIDC_SCOPES", "openid,email")
        settings = fresh_settings_module.Settings()
        assert settings.oidc_scopes == ["openid", "email"]

    def test_unset_uses_documented_default(self, monkeypatch, fresh_settings_module) -> None:
        monkeypatch.delenv("RAI_OIDC_SCOPES", raising=False)
        settings = fresh_settings_module.Settings()
        assert settings.oidc_scopes == ["openid", "email", "profile"]


class TestMultiReplicaFlag:
    def test_defaults_false(self, monkeypatch, fresh_settings_module) -> None:
        monkeypatch.delenv("RAI_MULTI_REPLICA", raising=False)
        settings = fresh_settings_module.Settings()
        assert settings.multi_replica is False

    def test_can_be_enabled(self, monkeypatch, fresh_settings_module) -> None:
        monkeypatch.setenv("RAI_MULTI_REPLICA", "true")
        settings = fresh_settings_module.Settings()
        assert settings.multi_replica is True


class TestMultiReplicaProblems:
    def test_sqlite_and_memory_both_flagged(self, fresh_settings_module) -> None:
        problems = fresh_settings_module.multi_replica_problems("sqlite", "memory")
        assert len(problems) == 2
        assert any("SQLite" in p for p in problems)
        assert any("rate limiting" in p for p in problems)

    def test_postgres_and_redis_is_clean(self, fresh_settings_module) -> None:
        problems = fresh_settings_module.multi_replica_problems("postgresql", "redis")
        assert problems == []

    def test_only_sqlite_flagged_when_redis_configured(self, fresh_settings_module) -> None:
        problems = fresh_settings_module.multi_replica_problems("sqlite", "redis")
        assert len(problems) == 1
        assert "SQLite" in problems[0]

    def test_only_memory_flagged_when_postgres_configured(self, fresh_settings_module) -> None:
        problems = fresh_settings_module.multi_replica_problems("postgresql", "memory")
        assert len(problems) == 1
        assert "rate limiting" in problems[0]
