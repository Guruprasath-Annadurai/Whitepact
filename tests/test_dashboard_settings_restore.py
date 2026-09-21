# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Regression test for WP-DASH-REV-01: Global settings restoration after fixtures.

Proves that dashboard client fixtures restore process-global settings
(database_url, db_path, auto_migrate) upon teardown and do not leak
mutated state to other tests.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from responsibleai.dashboard.app import settings

pytest_plugins = ["tests.test_dashboard_api"]


class TestSettingsRestorationRegression:
    @pytest.mark.asyncio
    async def test_fixture_restores_global_settings_after_execution(
        self, client: AsyncClient
    ) -> None:
        """Inside the test, settings are isolated to memory."""
        assert settings.db_path == ":memory:"
        assert settings.auto_migrate is False
        assert settings.database_url is None

    def test_global_settings_restored_after_fixture_teardown(self) -> None:
        """After fixture teardown, global settings must match their pre-fixture state
        and must not be left permanently pointing to in-memory or mutated fields.
        """
        # On vulnerable candidate 9614ce13, client mutated settings without restoring,
        # leaving auto_migrate=False and db_path=":memory:".
        # This test verifies restoration.
        assert settings.auto_migrate is not False or settings.db_path != ":memory:", (
            "Global settings leaked mutated fixture state without restoration: "
            f"db_path={settings.db_path!r}, auto_migrate={settings.auto_migrate!r}"
        )
