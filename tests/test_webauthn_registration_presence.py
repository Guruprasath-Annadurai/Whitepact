# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Registration must enforce presence independently of verification policy."""

import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from responsibleai.enterprise.security.webauthn import (
    FLAG_UP,
    b64url_decode,
    b64url_encode,
    verify_registration,
)
from tests.webauthn_fakes import registration_blob


@pytest.mark.parametrize("require_uv", [False, True])
@pytest.mark.parametrize("present", [False, True])
def test_registration_requires_user_presence(require_uv, present):
    challenge = b"isolated-registration-presence-challenge"
    client, authenticator, _, _ = registration_blob(
        rp_id="localhost",
        origin="http://localhost:8123",
        challenge=challenge,
        private_key=ec.generate_private_key(ec.SECP256R1()),
    )
    data = bytearray(b64url_decode(authenticator))
    if not present:
        data[32] &= ~FLAG_UP

    def verify():
        return verify_registration(
            client_data_b64=client,
            authenticator_data_b64=b64url_encode(bytes(data)),
            expected_origin="http://localhost:8123",
            expected_rp_id="localhost",
            expected_challenge=challenge,
            require_uv=require_uv,
        )

    if present:
        assert verify()[3] & FLAG_UP
    else:
        with pytest.raises(ValueError, match="user-present flag required"):
            verify()
