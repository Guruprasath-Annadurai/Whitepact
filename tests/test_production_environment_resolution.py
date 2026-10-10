# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""One definition of "production", used by every security-relevant gate.

Before ``responsibleai.environment`` the isolation gate read only ``ENVIRONMENT`` and only the exact
word ``production``. ``WHITEPACT_ENV=production`` alone, or ``ENVIRONMENT=prod``, left the
unisolated-execution opt-in working in a deployment every other module called production.
"""

from __future__ import annotations

import itertools
from typing import Any

import pytest

from responsibleai import environment
from responsibleai.environment import (
    ENVIRONMENT_VARIABLES,
    NON_PRODUCTION_NAMES,
    PRODUCTION_ALIASES,
    ConflictingEnvironmentError,
    effective_environment_name,
    is_production,
    require_consistent,
    resolve,
)
from responsibleai.governance.execution import InternalToolExecutor
from responsibleai.isolation.errors import IsolationError
from responsibleai.isolation.mode import (
    SYNTHETIC_HOST_TOOL_ENV,
    UNISOLATED_EXECUTION_ENV,
    synthetic_host_tool_allowed,
    unisolated_execution_allowed,
)
from tests.test_isolation_real_tool_e2e import _action, _authorization

PRODUCTION_SPELLINGS = ["production", "PRODUCTION", "Prod", " prod ", "prd", "LIVE", "live"]


@pytest.fixture
def clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> pytest.MonkeyPatch:
    for name in (*ENVIRONMENT_VARIABLES, UNISOLATED_EXECUTION_ENV, SYNTHETIC_HOST_TOOL_ENV):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)  # no stray .env
    return monkeypatch


class TestResolution:
    def test_nothing_set_is_development_and_not_production(self, clean: Any) -> None:
        assert is_production() is False
        assert effective_environment_name() == "development"

    @pytest.mark.parametrize("variable", ENVIRONMENT_VARIABLES)
    @pytest.mark.parametrize("spelling", PRODUCTION_SPELLINGS)
    def test_any_variable_with_any_alias_is_production(
        self, clean: Any, variable: str, spelling: str
    ) -> None:
        clean.setenv(variable, spelling)
        assert is_production() is True
        assert effective_environment_name() == "production"

    @pytest.mark.parametrize("variable", [v for v in ENVIRONMENT_VARIABLES if v != "ENV"])
    @pytest.mark.parametrize("name", sorted(NON_PRODUCTION_NAMES))
    def test_known_non_production_names_are_not_production(
        self, clean: Any, variable: str, name: str
    ) -> None:
        clean.setenv(variable, name)
        assert is_production() is False

    @pytest.mark.parametrize(
        ("production_var", "other_var"),
        [
            (a, b)
            for a, b in itertools.permutations(ENVIRONMENT_VARIABLES, 2)
            if "ENV" not in (a, b) or True
        ],
    )
    def test_a_conflict_fails_safe_to_production_and_refuses_startup(
        self, clean: Any, production_var: str, other_var: str
    ) -> None:
        clean.setenv(production_var, "production")
        clean.setenv(other_var, "development")
        assert resolve().conflicting is True
        assert is_production() is True
        with pytest.raises(ConflictingEnvironmentError, match="disagree"):
            require_consistent()

    @pytest.mark.parametrize("typo", ["prodution", "prod-eu", "prodcution", "1", "yes"])
    def test_an_unrecognised_name_counts_as_production_and_refuses_startup(
        self, clean: Any, typo: str
    ) -> None:
        clean.setenv("ENVIRONMENT", typo)
        assert is_production() is True
        with pytest.raises(ConflictingEnvironmentError, match="Unrecognised"):
            require_consistent()

    def test_the_posix_ENV_rc_file_variable_is_not_mistaken_for_a_typo(self, clean: Any) -> None:
        clean.setenv("ENV", "/home/someone/.shrc")
        assert is_production() is False
        require_consistent()

    def test_dotenv_file_is_read_and_a_process_variable_overrides_it(
        self, clean: Any, tmp_path: Any
    ) -> None:
        (tmp_path / ".env").write_text("WHITEPACT_ENV=production\n")
        assert is_production() is True
        clean.setenv("WHITEPACT_ENV", "development")  # same name: the process value wins
        assert resolve().values["WHITEPACT_ENV"] == "development"
        assert is_production() is False

    def test_dotenv_production_conflicts_with_a_process_development_name(
        self, clean: Any, tmp_path: Any
    ) -> None:
        (tmp_path / ".env").write_text("ENVIRONMENT=production\n")
        clean.setenv("WHITEPACT_ENV", "development")
        assert resolve().conflicting is True and is_production() is True

    def test_explicit_mapping_does_not_touch_the_process(self) -> None:
        assert is_production({"RAI_ENV": "prod"}) is True
        assert is_production({"RAI_ENV": "dev"}) is False


class TestNoProductionConfigurationCanEnableUnisolatedExecution:
    @pytest.mark.parametrize("variable", ENVIRONMENT_VARIABLES)
    @pytest.mark.parametrize("spelling", PRODUCTION_SPELLINGS)
    def test_the_opt_in_is_ignored(self, clean: Any, variable: str, spelling: str) -> None:
        clean.setenv(UNISOLATED_EXECUTION_ENV, "1")
        clean.setenv(SYNTHETIC_HOST_TOOL_ENV, "1")
        clean.setenv(variable, spelling)
        assert unisolated_execution_allowed() is False
        assert synthetic_host_tool_allowed() is False

    @pytest.mark.parametrize(
        ("a", "b"), list(itertools.permutations([v for v in ENVIRONMENT_VARIABLES], 2))
    )
    def test_conflicting_settings_never_enable_it(self, clean: Any, a: str, b: str) -> None:
        clean.setenv(UNISOLATED_EXECUTION_ENV, "1")
        clean.setenv(SYNTHETIC_HOST_TOOL_ENV, "1")
        clean.setenv(a, "production")
        clean.setenv(b, "development")
        assert unisolated_execution_allowed() is False
        assert synthetic_host_tool_allowed() is False

    @pytest.mark.parametrize("typo", ["prodution", "prod-eu", "1"])
    def test_a_typo_never_enables_it(self, clean: Any, typo: str) -> None:
        clean.setenv(UNISOLATED_EXECUTION_ENV, "1")
        clean.setenv("WHITEPACT_ENV", typo)
        assert unisolated_execution_allowed() is False

    def test_non_production_with_the_explicit_opt_in_still_works(self, clean: Any) -> None:
        clean.setenv(UNISOLATED_EXECUTION_ENV, "1")
        clean.setenv("WHITEPACT_ENV", "development")
        assert unisolated_execution_allowed() is True
        clean.setenv(SYNTHETIC_HOST_TOOL_ENV, "1")
        assert synthetic_host_tool_allowed() is True

    @pytest.mark.parametrize("variable", ENVIRONMENT_VARIABLES)
    @pytest.mark.asyncio
    async def test_the_executor_refuses_a_real_tool_without_a_broker(
        self, clean: Any, variable: str
    ) -> None:
        clean.setenv(UNISOLATED_EXECUTION_ENV, "1")
        clean.setenv(variable, "production")
        executor = InternalToolExecutor(broker=object())
        executor._broker = None
        action = _action("rai_scan")
        with pytest.raises(IsolationError, match="strictly forbidden in production"):
            await executor.execute(_authorization(action), action)


class TestSettingsAgreeWithTheGate:
    @pytest.mark.parametrize("variable", [v for v in ENVIRONMENT_VARIABLES])
    def test_settings_see_production_whenever_the_gate_does(
        self, clean: Any, variable: str
    ) -> None:
        from responsibleai.dashboard.config import Settings

        clean.setenv(variable, "production")
        # Production Settings demand a database etc.; the point is that it is treated as production.
        with pytest.raises(ValueError, match="(?i)production"):
            Settings(_env_file=None)

    def test_settings_refuse_conflicting_environment_variables(self, clean: Any) -> None:
        from responsibleai.dashboard.config import Settings

        clean.setenv("WHITEPACT_ENV", "development")
        clean.setenv("ENVIRONMENT", "production")
        with pytest.raises(ValueError, match="disagree"):
            Settings(_env_file=None)

    def test_a_development_settings_object_is_unaffected(self, clean: Any) -> None:
        from responsibleai.dashboard.config import Settings

        clean.setenv("WHITEPACT_ENV", "development")
        assert Settings(_env_file=None).is_production is False

    def test_module_constants_are_not_diverging_copies(self) -> None:
        from responsibleai.dashboard import config

        assert config.PRODUCTION_ENVIRONMENTS is environment.PRODUCTION_ALIASES
        assert PRODUCTION_ALIASES >= {"production", "prod"}
