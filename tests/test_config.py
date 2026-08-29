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
    def test_comma_separated_string_does_not_crash(
        self, monkeypatch, fresh_settings_module
    ) -> None:
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
    def test_comma_separated_string_does_not_crash(
        self, monkeypatch, fresh_settings_module
    ) -> None:
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
    def test_comma_separated_string_does_not_crash(
        self, monkeypatch, fresh_settings_module
    ) -> None:
        monkeypatch.setenv("RAI_OIDC_SCOPES", "openid,email")
        settings = fresh_settings_module.Settings()
        assert settings.oidc_scopes == ["openid", "email"]

    def test_unset_uses_documented_default(self, monkeypatch, fresh_settings_module) -> None:
        monkeypatch.delenv("RAI_OIDC_SCOPES", raising=False)
        settings = fresh_settings_module.Settings()
        assert settings.oidc_scopes == ["openid", "email", "profile"]


class TestOidcHumanIndicatorValuesEnvParsing:
    def test_comma_separated_string_does_not_crash(
        self, monkeypatch, fresh_settings_module
    ) -> None:
        monkeypatch.setenv("RAI_OIDC_HUMAN_INDICATOR_VALUES", "pwd,mfa")
        settings = fresh_settings_module.Settings()
        assert settings.oidc_human_indicator_values == ["pwd", "mfa"]

    def test_unset_uses_documented_default(self, monkeypatch, fresh_settings_module) -> None:
        monkeypatch.delenv("RAI_OIDC_HUMAN_INDICATOR_VALUES", raising=False)
        settings = fresh_settings_module.Settings()
        assert settings.oidc_human_indicator_values == ["pwd", "mfa", "otp"]

    def test_human_indicator_claim_unset_by_default(
        self, monkeypatch, fresh_settings_module
    ) -> None:
        monkeypatch.delenv("RAI_OIDC_HUMAN_INDICATOR_CLAIM", raising=False)
        settings = fresh_settings_module.Settings()
        assert settings.oidc_human_indicator_claim is None


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


class TestWhitepactEnvVarPrecedence:
    """MIGRATION_WHITEPACT_V2.md Section 5: WHITEPACT_ is the preferred
    prefix; RAI_ is the legacy prefix, kept fully functional. If both are
    set for the same field, WHITEPACT_ wins."""

    def test_new_prefix_used_when_only_new_is_set(self, monkeypatch, fresh_settings_module) -> None:
        monkeypatch.setenv("WHITEPACT_DB_PATH", "/tmp/new-only.db")
        settings = fresh_settings_module.Settings()
        assert settings.db_path == "/tmp/new-only.db"

    def test_legacy_prefix_still_works_alone(self, monkeypatch, fresh_settings_module) -> None:
        monkeypatch.setenv("RAI_DB_PATH", "/tmp/legacy-only.db")
        settings = fresh_settings_module.Settings()
        assert settings.db_path == "/tmp/legacy-only.db"

    def test_new_prefix_wins_when_both_are_set(self, monkeypatch, fresh_settings_module) -> None:
        monkeypatch.setenv("RAI_DB_PATH", "/tmp/legacy.db")
        monkeypatch.setenv("WHITEPACT_DB_PATH", "/tmp/new.db")
        settings = fresh_settings_module.Settings()
        assert settings.db_path == "/tmp/new.db"

    def test_precedence_holds_for_a_second_unrelated_field(
        self, monkeypatch, fresh_settings_module
    ) -> None:
        # Not just db_path — the precedence is a source-ordering rule that
        # applies uniformly across all fields, not a per-field special case.
        monkeypatch.setenv("RAI_BRAND_NAME", "LegacyBrand")
        monkeypatch.setenv("WHITEPACT_BRAND_NAME", "WhitePact")
        settings = fresh_settings_module.Settings()
        assert settings.brand_name == "WhitePact"


class TestOtelHeadersDict:
    def test_empty_string_returns_empty_dict(self, fresh_settings_module) -> None:
        settings = fresh_settings_module.Settings(otel_headers="")
        assert settings.otel_headers_dict == {}

    def test_single_pair_parsed(self, fresh_settings_module) -> None:
        settings = fresh_settings_module.Settings(otel_headers="x-api-key=secret")
        assert settings.otel_headers_dict == {"x-api-key": "secret"}

    def test_multiple_pairs_parsed(self, fresh_settings_module) -> None:
        settings = fresh_settings_module.Settings(otel_headers="a=1,b=2")
        assert settings.otel_headers_dict == {"a": "1", "b": "2"}

    def test_pair_without_equals_sign_is_skipped(self, fresh_settings_module) -> None:
        settings = fresh_settings_module.Settings(otel_headers="a=1,not-a-pair,b=2")
        assert settings.otel_headers_dict == {"a": "1", "b": "2"}


class TestDbDir:
    def test_memory_path_returns_current_dir(self, fresh_settings_module) -> None:
        settings = fresh_settings_module.Settings(db_path=":memory:")
        assert settings.db_dir == fresh_settings_module.Path(".")

    def test_file_path_returns_parent_dir(self, fresh_settings_module, tmp_path) -> None:
        db_file = tmp_path / "sub" / "data.db"
        settings = fresh_settings_module.Settings(db_path=str(db_file))
        assert settings.db_dir == db_file.parent


class TestEnsureDbDir:
    def test_creates_parent_dir_for_file_backed_db(self, fresh_settings_module, tmp_path) -> None:
        db_file = tmp_path / "nested" / "data.db"
        settings = fresh_settings_module.Settings(db_path=str(db_file))
        fresh_settings_module._ensure_db_dir(settings)
        assert db_file.parent.is_dir()

    def test_memory_path_does_not_touch_filesystem(self, fresh_settings_module) -> None:
        settings = fresh_settings_module.Settings(db_path=":memory:")
        fresh_settings_module._ensure_db_dir(settings)  # must not raise


class TestWarnDeprecatedEnvVars:
    def test_warns_when_only_legacy_var_is_set(self, fresh_settings_module) -> None:
        with pytest.warns(DeprecationWarning, match="RAI_DB_PATH.*WHITEPACT_DB_PATH"):
            found = fresh_settings_module.warn_deprecated_env_vars({"RAI_DB_PATH": "x"})
        assert found == ["RAI_DB_PATH"]

    def test_no_warning_when_new_prefix_also_set(self, fresh_settings_module) -> None:
        import warnings as warnings_module

        with warnings_module.catch_warnings():
            warnings_module.simplefilter("error")  # any warning fails the test
            found = fresh_settings_module.warn_deprecated_env_vars(
                {"RAI_DB_PATH": "x", "WHITEPACT_DB_PATH": "y"}
            )
        assert found == []

    def test_no_warning_when_neither_set(self, fresh_settings_module) -> None:
        found = fresh_settings_module.warn_deprecated_env_vars({})
        assert found == []

    def test_unrelated_rai_prefixed_var_that_is_not_a_real_field_is_ignored(
        self,
        fresh_settings_module,
    ) -> None:
        # Scoped to Settings.model_fields, not a blind RAI_ scan — a typo'd
        # or unrelated variable shouldn't be reported as "a legacy setting
        # in effect" when it was never a real setting at all.
        found = fresh_settings_module.warn_deprecated_env_vars({"RAI_NOT_A_REAL_FIELD": "x"})
        assert found == []

    def test_case_insensitive_like_the_settings_themselves(self, fresh_settings_module) -> None:
        with pytest.warns(DeprecationWarning):
            found = fresh_settings_module.warn_deprecated_env_vars({"rai_db_path": "x"})
        assert found == ["RAI_DB_PATH"]

    def test_get_settings_triggers_the_scan_on_first_call_only(
        self,
        monkeypatch,
        fresh_settings_module,
    ) -> None:
        monkeypatch.setenv("RAI_DB_PATH", ":memory:")
        with pytest.warns(DeprecationWarning):
            fresh_settings_module.get_settings()
        # Second call hits the module-level cache — no repeated warning.
        import warnings as warnings_module

        with warnings_module.catch_warnings():
            warnings_module.simplefilter("error")
            fresh_settings_module.get_settings()
