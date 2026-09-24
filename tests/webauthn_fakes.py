# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Build valid WebAuthn authenticatorData and signatures for tests."""

from __future__ import annotations

import hashlib
import json

import cbor2
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ec import ECDSA
from cryptography.hazmat.primitives.hashes import SHA256

from responsibleai.enterprise.security.webauthn import (
    FLAG_AT,
    FLAG_UP,
    FLAG_UV,
    b64url_encode,
    rp_id_hash,
)


def _coords(public_key: ec.EllipticCurvePublicKey) -> tuple[bytes, bytes]:
    numbers = public_key.public_numbers()
    return numbers.x.to_bytes(32, "big"), numbers.y.to_bytes(32, "big")


def client_data(*, typ: str, origin: str, challenge: bytes) -> str:
    payload = {"type": typ, "origin": origin, "challenge": b64url_encode(challenge)}
    return b64url_encode(json.dumps(payload, separators=(",", ":")).encode())


def registration_blob(
    *, rp_id: str, origin: str, challenge: bytes, private_key: ec.EllipticCurvePrivateKey
) -> tuple[str, str, str, bytes]:
    public = private_key.public_key()
    x, y = _coords(public)
    cred_id = hashlib.sha256(x + y).digest()[:16]
    cose = cbor2.dumps({1: 2, 3: -7, -1: 1, -2: x, -3: y})
    flags = FLAG_UP | FLAG_UV | FLAG_AT
    auth = (
        rp_id_hash(rp_id)
        + bytes([flags])
        + (0).to_bytes(4, "big")
        + (b"\x00" * 16)
        + len(cred_id).to_bytes(2, "big")
        + cred_id
        + cose
    )
    return (
        client_data(typ="webauthn.create", origin=origin, challenge=challenge),
        b64url_encode(auth),
        b64url_encode(cred_id),
        cred_id,
    )


def assertion_blob(
    *,
    rp_id: str,
    origin: str,
    challenge: bytes,
    private_key: ec.EllipticCurvePrivateKey,
    sign_count: int = 1,
) -> tuple[str, str, str]:
    flags = FLAG_UP | FLAG_UV
    auth = rp_id_hash(rp_id) + bytes([flags]) + sign_count.to_bytes(4, "big")
    cdata = client_data(typ="webauthn.get", origin=origin, challenge=challenge)
    raw_client = json.dumps(
        {"type": "webauthn.get", "origin": origin, "challenge": b64url_encode(challenge)},
        separators=(",", ":"),
    ).encode()
    message = auth + hashlib.sha256(raw_client).digest()
    signature = private_key.sign(message, ECDSA(SHA256()))
    return cdata, b64url_encode(auth), b64url_encode(signature)
