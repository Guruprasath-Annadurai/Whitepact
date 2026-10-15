# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Development-only switches are refused in production, whichever way production is spelled."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from responsibleai.dashboard.config import Settings
from responsibleai.environment import ENVIRONMENT_VARIABLES

UNSAFE = [
    "oidc_skip_verification",
    "vc_skip_verification",
    "mcp_http_allow_unauthenticated_demo",
    "web_auth_dev_tokens",
]


@pytest.fixture
def production(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for name in ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("WHITEPACT_DATABASE_URL", "postgresql+asyncpg://u:p@db.example/wp")
    monkeypatch.setenv("WHITEPACT_FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("WHITEPACT_MCP_TRUST_DOMAIN", "enterprise")
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    return monkeypatch


def test_a_clean_production_configuration_is_accepted(production) -> None:
    assert Settings(_env_file=None).is_production is True


@pytest.mark.parametrize("flag", UNSAFE)
def test_each_development_only_switch_is_refused_in_production(production, flag: str) -> None:
    with pytest.raises(ValueError, match=flag):
        Settings(_env_file=None, **{flag: True})


def test_an_insecure_session_cookie_is_refused_in_production(production) -> None:
    with pytest.raises(ValueError, match="web_session_secure"):
        Settings(_env_file=None, web_session_secure=False)


@pytest.mark.parametrize(
    "variable", ["ENVIRONMENT", "RAI_ENV", "RAI_ENVIRONMENT", "WHITEPACT_ENVIRONMENT"]
)
@pytest.mark.parametrize("spelling", ["prod", "PRODUCTION", "live"])
def test_every_production_spelling_triggers_the_same_refusal(
    production, variable, spelling
) -> None:
    production.delenv("WHITEPACT_ENV", raising=False)
    production.setenv(variable, spelling)
    with pytest.raises(ValueError, match="vc_skip_verification"):
        Settings(_env_file=None, vc_skip_verification=True)


def test_the_switches_are_still_available_outside_production(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    for name in ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("WHITEPACT_ENV", "development")
    settings = Settings(
        _env_file=None,
        oidc_skip_verification=True,
        vc_skip_verification=True,
        web_auth_dev_tokens=True,
        web_session_secure=False,
    )
    assert settings.is_production is False


def test_a_dotenv_file_cannot_smuggle_a_dev_switch_into_production(production, tmp_path) -> None:
    (tmp_path / ".env").write_text("WHITEPACT_VC_SKIP_VERIFICATION=true\n")
    with pytest.raises(ValueError, match="vc_skip_verification"):
        Settings()


def test_whitepact_prefixed_dotenv_values_are_honoured_with_the_documented_precedence(
    monkeypatch, tmp_path
) -> None:
    """A WHITEPACT_ line in .env used to be ignored (only RAI_ was read there)."""
    monkeypatch.chdir(tmp_path)
    for name in ENVIRONMENT_VARIABLES + ("WHITEPACT_RATE_LIMIT_DEFAULT", "RAI_RATE_LIMIT_DEFAULT"):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / ".env").write_text(
        "RAI_RATE_LIMIT_DEFAULT=1/minute\nWHITEPACT_RATE_LIMIT_DEFAULT=2/minute\n"
    )
    assert Settings().rate_limit_default == "2/minute"  # WHITEPACT_ beats RAI_ inside .env
    monkeypatch.setenv("RAI_RATE_LIMIT_DEFAULT", "3/minute")
    assert Settings().rate_limit_default == "3/minute"  # a real environment variable beats .env
    monkeypatch.setenv("WHITEPACT_RATE_LIMIT_DEFAULT", "4/minute")
    assert Settings().rate_limit_default == "4/minute"
    assert Settings(_env_file=None).rate_limit_default == "4/minute"
    monkeypatch.delenv("WHITEPACT_RATE_LIMIT_DEFAULT")
    monkeypatch.delenv("RAI_RATE_LIMIT_DEFAULT")
    assert Settings(_env_file=None).rate_limit_default not in {"1/minute", "2/minute"}
