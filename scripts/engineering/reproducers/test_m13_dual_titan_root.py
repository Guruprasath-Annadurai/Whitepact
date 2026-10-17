# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Run the immutable authority boundary with explicit optional flag values."""

import pytest
from scripts.engineering.reproducers.test_m13_corrective_authority import (
    test_unverified_owner_cannot_activate_root_with_default_flags as assert_unverified_denied,
)

from responsibleai.enterprise.authority.service import CustomerAuthorityService


@pytest.mark.asyncio
@pytest.mark.parametrize("require_identity_assurance", [False, True])
async def test_unverified_owner_denied_with_explicit_assurance_flag(
    monkeypatch, require_identity_assurance: bool
) -> None:
    original = CustomerAuthorityService.initiate_root_bootstrap

    async def initiate(self, actor, **kwargs):
        return await original(
            self, actor, **kwargs, require_identity_assurance=require_identity_assurance
        )

    monkeypatch.setattr(CustomerAuthorityService, "initiate_root_bootstrap", initiate)
    await assert_unverified_denied()
