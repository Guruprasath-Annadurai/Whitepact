# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Production startup preflight for Launch Cell B operations contract."""

from __future__ import annotations

from typing import TYPE_CHECKING

from responsibleai.enterprise.preflight import HostedEnterpriseSecurityError
from responsibleai.operations.production_config import collect_production_configuration_errors

if TYPE_CHECKING:
    from responsibleai.dashboard.config import Settings


def assert_production_configuration_safe(settings: Settings) -> None:
    """Fail closed at startup when production violates the operations contract."""
    errors = collect_production_configuration_errors(settings)
    if errors:
        raise HostedEnterpriseSecurityError(
            "Production configuration contract violated: " + "; ".join(sorted(set(errors)))
        )
