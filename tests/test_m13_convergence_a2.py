# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Additional genuine-signature A2 negatives; no elevated session is seeded."""

import base64
import hashlib
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ec import ECDSA
from cryptography.hazmat.primitives.hashes import SHA256
from sqlalchemy import func, select, update

from responsibleai.db.engine import (
    governance_root_authority_records,
    passkey_credentials,
    web_users,
)
from responsibleai.enterprise.errors import EnterpriseError
from tests.test_sovereign_authority import owner as owner
from tests.test_sovereign_authority import root


def decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


@pytest.mark.asyncio
@pytest.mark.parametrize("owner", ["postgres"], indirect=True)
@pytest.mark.parametrize(
    "fault", ["unverified_email", "uv_false", "forged_challenge", "revoked_passkey"]
)
async def test_a2_rejects_invalid_current_identity_or_assertion(owner, fault):
    service, actor, parameters = await root(owner, prepare_only=True)
    engine, _, _, _, _, private, credential, *_ = owner
    assertion = parameters["webauthn_assertion"]
    if fault in {"unverified_email", "revoked_passkey"}:
        async with engine.raw.begin() as conn:
            if fault == "unverified_email":
                await conn.execute(
                    update(web_users)
                    .where(web_users.c.id == actor.user_id)
                    .values(
                        email_verified_at=None,
                        verification_status="UNVERIFIED",
                    )
                )
            else:
                # Persisted revocation fault injection, not a claim that the
                # customer authenticator-removal journey has been qualified.
                await conn.execute(
                    update(passkey_credentials)
                    .where(passkey_credentials.c.credential_id == credential)
                    .values(status="REVOKED")
                )
    else:
        client = decode(assertion["client_data_json"])
        authenticator = bytearray(decode(assertion["authenticator_data"]))
        if fault == "uv_false":
            authenticator[32] &= ~0x04
        else:
            payload = json.loads(client)
            payload["challenge"] = encode(b"not-a-server-issued-challenge")
            client = json.dumps(payload, separators=(",", ":")).encode()
        # A real enrolled key signs the negative assertion. Rejection must not
        # depend solely on a broken signature masking UV/challenge validation.
        signature = private.sign(
            bytes(authenticator) + hashlib.sha256(client).digest(), ECDSA(SHA256())
        )
        assertion.update(
            client_data_json=encode(client),
            authenticator_data=encode(bytes(authenticator)),
            signature=encode(signature),
        )
    with pytest.raises(EnterpriseError):
        await service.complete_root_bootstrap(actor, **parameters)
    async with engine.raw.connect() as conn:
        assert (
            await conn.scalar(
                select(func.count())
                .select_from(governance_root_authority_records)
                .where(governance_root_authority_records.c.organization_id == actor.org_id)
            )
            == 0
        )
