# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

import pytest

from responsibleai.sovereign.errors import SovereignTenantIsolationError
from responsibleai.sovereign.tenant import assert_same_organization


def test_cross_tenant_denied_without_disclosure() -> None:
    with pytest.raises(SovereignTenantIsolationError) as exc:
        assert_same_organization("org-a", "org-b", resource_kind="trace")
    assert "not found" in str(exc.value).lower()
