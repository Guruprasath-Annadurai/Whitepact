"""Phase 2 (Enterprise Neural directive) — the self-describing
encrypted envelope format actual data gets stored as, once a caller has
a DEK from a `KeyProvider`. See
`docs/enterprise-neural/02_PHASE2_DESIGN.md` Sec 3.3, 3.10.

Envelope layout: `<key_id string> \\x00 <12-byte nonce> <AES-256-GCM
ciphertext+tag>`. The embedded `KeyId` is bound into the ciphertext's
authentication tag via AEAD associated data (`KeyId.to_aad()`) — it is
not merely concatenated in front of it — so tampering with the embedded
`KeyId` breaks the authentication tag the same as tampering with the
ciphertext itself.
"""

from __future__ import annotations

import base64
import binascii
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from responsibleai.governance.crypto.types import DecryptionError, EnvelopeFormatError, KeyId

_NONCE_SIZE_BYTES = 12
_SEPARATOR = b"\x00"


def encrypt_envelope(dek: bytes, key_id: KeyId, plaintext: bytes) -> bytes:
    """Encrypt *plaintext* under *dek*, producing a self-describing
    envelope carrying *key_id* so a future decryptor can identify which
    key it needs without external context.

    No parameter here accepts a caller-supplied nonce — one is always
    generated internally via `os.urandom`, so nonce reuse cannot occur
    through this public API (a required Phase 2 misuse-test property).
    """
    nonce = os.urandom(_NONCE_SIZE_BYTES)
    ciphertext = AESGCM(dek).encrypt(nonce, plaintext, key_id.to_aad())
    return key_id.to_string().encode("utf-8") + _SEPARATOR + nonce + ciphertext


def decrypt_envelope(dek: bytes, expected_key_id: KeyId, envelope: bytes) -> bytes:
    """Decrypt *envelope*, refusing unless its embedded `KeyId` matches
    *expected_key_id* (defense in depth beyond the AAD binding itself —
    a caller that resolved the wrong DEK for the wrong purpose/tenant
    is caught here even before the AEAD tag is checked) and its
    authentication tag verifies."""
    if _SEPARATOR not in envelope:
        raise EnvelopeFormatError("Envelope is missing the KeyId separator")
    key_id_bytes, rest = envelope.split(_SEPARATOR, 1)
    try:
        embedded_key_id = KeyId.from_string(key_id_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise EnvelopeFormatError(f"Envelope KeyId is malformed: {exc}") from exc
    if embedded_key_id != expected_key_id:
        raise DecryptionError(
            "Envelope's embedded KeyId does not match the expected key — "
            "possible tenant/purpose/version confusion or tampering"
        )
    if len(rest) < _NONCE_SIZE_BYTES:
        raise EnvelopeFormatError("Envelope is too short to contain a nonce")
    nonce, ciphertext = rest[:_NONCE_SIZE_BYTES], rest[_NONCE_SIZE_BYTES:]
    try:
        return AESGCM(dek).decrypt(nonce, ciphertext, expected_key_id.to_aad())
    except InvalidTag as exc:
        raise DecryptionError(
            "Failed to decrypt envelope — corrupted ciphertext or tampered metadata"
        ) from exc


def encode_envelope(envelope: bytes) -> str:
    """Base64-encode an envelope for storage in a text column, matching
    the existing project convention (`db/encryption.py`'s Fernet tokens
    are also stored as base64 text, not raw bytes)."""
    return base64.urlsafe_b64encode(envelope).decode("ascii")


def decode_envelope(encoded: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(encoded.encode("ascii"))
    except (binascii.Error, ValueError) as exc:
        raise EnvelopeFormatError(f"Envelope is not valid base64: {exc}") from exc
