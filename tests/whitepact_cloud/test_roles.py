# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.whitepact_cloud.roles import (
    CloudRole,
    is_sensitive_permission,
    role_allows,
)


def test_owner_role_allows_any_permission() -> None:
    assert role_allows(CloudRole.OWNER, "cloud.anything.custom")


def test_developer_cannot_iam_write() -> None:
    assert role_allows(CloudRole.DEVELOPER, "cloud.iam.write") is False


def test_sensitive_permission_registry() -> None:
    assert is_sensitive_permission("cloud.iam.write")
    assert not is_sensitive_permission("cloud.infra.read")
