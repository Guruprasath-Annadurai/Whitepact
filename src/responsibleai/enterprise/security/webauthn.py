# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WebAuthn Level 3 ceremony validation for passkeys.

Private keys are never persisted. Challenges are server-generated, hashed,
short-lived, single-use, and bound to user/session/ceremony/origin/RP ID.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ec import (
    ECDSA,
    SECP256R1,
    EllipticCurvePublicKey,
    EllipticCurvePublicNumbers,
)
from cryptography.hazmat.primitives.hashes import SHA256

FLAG_UP = 0x01
FLAG_UV = 0x04
FLAG_AT = 0x40


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(value + padding)


def rp_id_hash(rp_id: str) -> bytes:
    return hashlib.sha256(rp_id.encode("ascii")).digest()


@dataclass(frozen=True)
class ClientData:
    type: str
    origin: str
    challenge: bytes
    raw: bytes


def parse_client_data(client_data_json_b64: str) -> ClientData:
    raw = b64url_decode(client_data_json_b64)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Malformed clientDataJSON") from exc
    challenge = b64url_decode(str(payload.get("challenge", "")))
    return ClientData(
        type=str(payload.get("type", "")),
        origin=str(payload.get("origin", "")),
        challenge=challenge,
        raw=raw,
    )


def parse_auth_data(auth_data: bytes) -> tuple[bytes, int, int, bytes | None, bytes | None]:
    if len(auth_data) < 37:
        raise ValueError("authenticatorData too short")
    rp_hash = auth_data[:32]
    flags = auth_data[32]
    sign_count = int.from_bytes(auth_data[33:37], "big")
    cred_id = None
    cose_key = None
    if flags & FLAG_AT:
        if len(auth_data) < 55:
            raise ValueError("attested credential data truncated")
        cred_len = int.from_bytes(auth_data[53:55], "big")
        rest = auth_data[55:]
        if len(rest) < cred_len:
            raise ValueError("credential id truncated")
        cred_id = rest[:cred_len]
        cose_key = rest[cred_len:]
    return rp_hash, flags, sign_count, cred_id, cose_key


def cose_ec2_uncompressed(cose_bytes: bytes) -> bytes:
    """Decode a COSE_Key EC2 P-256 public key to uncompressed 0x04||x||y.

    V1 supports ES256 (COSE alg -7, P-256) only. Other COSE algorithms are
    rejected. This is an interoperability limitation, not algorithm agility.
    """
    try:
        import cbor2
    except ImportError as exc:
        raise ValueError("cbor2 is required to parse COSE public keys") from exc
    obj = cbor2.loads(cose_bytes)
    if not isinstance(obj, dict):
        raise ValueError("COSE key is not a map")
    if obj.get(1) != 2 or obj.get(-1) != 1:
        raise ValueError("Only ES256 P-256 COSE keys are accepted")
    x = obj.get(-2)
    y = obj.get(-3)
    if not isinstance(x, (bytes, bytearray)) or not isinstance(y, (bytes, bytearray)):
        raise ValueError("COSE EC2 coordinates missing")
    if len(x) != 32 or len(y) != 32:
        raise ValueError("COSE EC2 coordinates have invalid length")
    return b"\x04" + bytes(x) + bytes(y)


def public_key_from_uncompressed(raw: bytes) -> EllipticCurvePublicKey:
    if len(raw) != 65 or raw[0] != 4:
        raise ValueError("Expected uncompressed P-256 public key")
    x = int.from_bytes(raw[1:33], "big")
    y = int.from_bytes(raw[33:65], "big")
    return EllipticCurvePublicNumbers(x, y, SECP256R1()).public_key()


def verify_ecdsa_p256(public_key: EllipticCurvePublicKey, message: bytes, signature: bytes) -> None:
    public_key.verify(signature, message, ECDSA(SHA256()))


def verify_assertion(
    *,
    client_data_b64: str,
    authenticator_data_b64: str,
    signature_b64: str,
    public_key_uncompressed: bytes,
    expected_type: str,
    expected_origin: str,
    expected_rp_id: str,
    expected_challenge: bytes,
    require_uv: bool,
    previous_sign_count: int,
) -> int:
    client = parse_client_data(client_data_b64)
    if client.type != expected_type:
        raise ValueError("WebAuthn ceremony type mismatch")
    if client.origin != expected_origin:
        raise ValueError("WebAuthn origin mismatch")
    if client.challenge != expected_challenge:
        raise ValueError("WebAuthn challenge mismatch")
    auth_data = b64url_decode(authenticator_data_b64)
    rp_hash, flags, sign_count, _cred_id, _cose = parse_auth_data(auth_data)
    if rp_hash != rp_id_hash(expected_rp_id):
        raise ValueError("WebAuthn RP ID hash mismatch")
    if not (flags & FLAG_UP):
        raise ValueError("WebAuthn user-present flag required")
    if require_uv and not (flags & FLAG_UV):
        raise ValueError("WebAuthn user verification required")
    if previous_sign_count and sign_count <= previous_sign_count:
        raise ValueError("WebAuthn sign count did not advance")
    message = auth_data + hashlib.sha256(client.raw).digest()
    try:
        verify_ecdsa_p256(
            public_key_from_uncompressed(public_key_uncompressed),
            message,
            b64url_decode(signature_b64),
        )
    except InvalidSignature as exc:
        raise ValueError("WebAuthn signature invalid") from exc
    return sign_count


def verify_registration(
    *,
    client_data_b64: str,
    authenticator_data_b64: str,
    expected_origin: str,
    expected_rp_id: str,
    expected_challenge: bytes,
    require_uv: bool,
) -> tuple[bytes, bytes, int, int]:
    client = parse_client_data(client_data_b64)
    if client.type != "webauthn.create":
        raise ValueError("Registration ceremony required")
    if client.origin != expected_origin:
        raise ValueError("WebAuthn origin mismatch")
    if client.challenge != expected_challenge:
        raise ValueError("WebAuthn challenge mismatch")
    auth_data = b64url_decode(authenticator_data_b64)
    rp_hash, flags, sign_count, cred_id, cose = parse_auth_data(auth_data)
    if rp_hash != rp_id_hash(expected_rp_id):
        raise ValueError("WebAuthn RP ID hash mismatch")
    if not (flags & FLAG_AT) or cred_id is None or cose is None:
        raise ValueError("Attested credential data required")
    if require_uv and not (flags & FLAG_UV):
        raise ValueError("WebAuthn user verification required")
    public_key = cose_ec2_uncompressed(cose)
    return cred_id, public_key, sign_count, flags
