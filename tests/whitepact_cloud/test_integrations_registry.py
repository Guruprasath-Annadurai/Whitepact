# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.whitepact_cloud.integrations import (
    CLOUDFLARE_ACCESS_API,
    CLOUDFLARE_ZERO_TRUST_DEVICE,
    HETZNER_TOKEN_REVOKE,
    WEBAUTHN_ENROLLMENT,
)


def test_external_integrations_documented_as_not_implemented() -> None:
    for status in (
        CLOUDFLARE_ACCESS_API,
        CLOUDFLARE_ZERO_TRUST_DEVICE,
        WEBAUTHN_ENROLLMENT,
        HETZNER_TOKEN_REVOKE,
    ):
        assert status.implemented is False
        assert status.blocker is not None
