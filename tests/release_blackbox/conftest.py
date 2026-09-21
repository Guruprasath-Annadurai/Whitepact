# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Shared fixtures for release black-box / resilience preparation tests."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.release_blackbox_prep


@pytest.fixture
def blackbox_campaign_context() -> dict[str, str]:
    """Metadata for campaign correlation — not a live tenant credential."""
    return {
        "campaign": "PREPARATION",
        "final_verdict": "PENDING_COMBINED_RC",
    }
