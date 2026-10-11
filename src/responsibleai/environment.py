# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""The single answer to "is this process a production deployment?".

Several modules used to answer that independently: one read only ``ENVIRONMENT`` and only the
exact word ``production``; others read ``WHITEPACT_ENV`` then ``RAI_ENV``; others a third order.
So ``WHITEPACT_ENV=production`` with no ``ENVIRONMENT`` left the isolation gate believing it was
a development machine, and ``ENVIRONMENT=prod`` was not production at all to that gate.

The rules here are deliberately one-directional. Information can only make the process *more*
restricted:

* every recognised variable is read (``WHITEPACT_ENV``, ``WHITEPACT_ENVIRONMENT``, ``RAI_ENV``,
  ``RAI_ENVIRONMENT``, ``ENVIRONMENT``, ``ENV``), as is the ``.env`` file the settings loader reads;
  a real process variable overrides the ``.env`` value for the same name;
* any production alias (``production``, ``prod``, ``prd``, ``live``; case and whitespace ignored)
  in *any* of them means production;
* variables that disagree (one production, one not) are a **conflict** and count as production.
  Startup code should refuse to run rather than guess, see :func:`require_consistent`;
* a value that is neither a production alias nor a known non-production name (a typo such as
  ``prodution``) is **unrecognised**. For restricting behaviour it counts as production. ``ENV``
  is exempt because POSIX shells use it for an unrelated rc-file path.

Nothing is inferred from infrastructure. A deployment that sets none of these is "development", the
documented default.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

ENVIRONMENT_VARIABLES: tuple[str, ...] = (
    "WHITEPACT_ENV",
    "WHITEPACT_ENVIRONMENT",
    "RAI_ENV",
    "RAI_ENVIRONMENT",
    "ENVIRONMENT",
    "ENV",
)
# ``ENV`` is a shell variable too (a path to an rc file); never treat its content as a typo.
_ADVISORY_ONLY: frozenset[str] = frozenset({"ENV"})

PRODUCTION_ALIASES: frozenset[str] = frozenset({"production", "prod", "prd", "live"})
NON_PRODUCTION_NAMES: frozenset[str] = frozenset(
    {
        "development",
        "dev",
        "local",
        "test",
        "testing",
        "ci",
        "staging",
        "stage",
        "qa",
        "uat",
        "sandbox",
        "demo",
        "preview",
    }
)


class ConflictingEnvironmentError(RuntimeError):
    """Raised at startup when the environment variables disagree about production."""


def _normalise(value: str) -> str:
    return value.strip().lower()


def is_production_name(name: str | None) -> bool:
    """True for an explicit production alias. An empty or unknown name is not one."""
    return bool(name) and _normalise(str(name)) in PRODUCTION_ALIASES


def _dotenv_values() -> dict[str, str]:
    path = Path(".env")
    try:
        if not path.is_file():
            return {}
        from dotenv import dotenv_values

        return {
            key.upper(): str(value)
            for key, value in dotenv_values(path).items()
            if value is not None
        }
    except Exception:  # an unreadable .env must not weaken or crash the check
        return {}


@dataclass(frozen=True)
class EnvironmentResolution:
    values: Mapping[str, str]
    production_variables: tuple[str, ...]
    non_production_variables: tuple[str, ...]
    unrecognised_variables: tuple[str, ...]

    @property
    def conflicting(self) -> bool:
        return bool(self.production_variables) and bool(self.non_production_variables)

    @property
    def is_production(self) -> bool:
        return bool(self.production_variables) or bool(self.unrecognised_variables)

    @property
    def explicitly_non_production(self) -> bool:
        """Positive evidence of a non-production setup: nothing production, nothing unknown.

        Unset everywhere is the documented development default and also qualifies.
        """
        return not self.is_production and not self.conflicting

    @property
    def name(self) -> str:
        """A single label for display and for legacy ``is_production_environment(name)`` calls."""
        if self.is_production:
            return "production"
        for variable in ENVIRONMENT_VARIABLES:
            if variable in self.values:
                return _normalise(self.values[variable])
        return "development"


def resolve(environ: Mapping[str, str] | None = None) -> EnvironmentResolution:
    """Read every recognised variable. ``environ`` defaults to the process environment + ``.env``."""
    if environ is None:
        merged = _dotenv_values()
        merged.update({k.upper(): v for k, v in os.environ.items()})
        source: Mapping[str, str] = merged
    else:
        source = {k.upper(): v for k, v in environ.items()}
    values = {
        variable: source[variable]
        for variable in ENVIRONMENT_VARIABLES
        if variable in source and _normalise(source[variable])
    }
    production: list[str] = []
    non_production: list[str] = []
    unrecognised: list[str] = []
    for variable, raw in values.items():
        name = _normalise(raw)
        if name in PRODUCTION_ALIASES:
            production.append(variable)
        elif name in NON_PRODUCTION_NAMES:
            non_production.append(variable)
        elif variable not in _ADVISORY_ONLY:
            unrecognised.append(variable)
    return EnvironmentResolution(
        values=values,
        production_variables=tuple(production),
        non_production_variables=tuple(non_production),
        unrecognised_variables=tuple(unrecognised),
    )


def is_production(environ: Mapping[str, str] | None = None) -> bool:
    """True if any recognised variable says production, they conflict, or one is unrecognised."""
    return resolve(environ).is_production


def effective_environment_name(environ: Mapping[str, str] | None = None) -> str:
    """``"production"`` whenever :func:`is_production`, else the first recognised value."""
    return resolve(environ).name


def require_consistent(environ: Mapping[str, str] | None = None) -> EnvironmentResolution:
    """Refuse to start on a conflict or an unrecognised value instead of guessing."""
    resolution = resolve(environ)
    if resolution.conflicting:
        raise ConflictingEnvironmentError(
            "Environment variables disagree about production "
            f"(production: {', '.join(resolution.production_variables)}; "
            f"non-production: {', '.join(resolution.non_production_variables)}). "
            "Set them consistently or unset the extras."
        )
    if resolution.unrecognised_variables and not resolution.production_variables:
        raise ConflictingEnvironmentError(
            "Unrecognised environment name in "
            f"{', '.join(resolution.unrecognised_variables)}. Use one of: "
            f"{', '.join(sorted(PRODUCTION_ALIASES | NON_PRODUCTION_NAMES))}."
        )
    return resolution
