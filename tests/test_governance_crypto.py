"""Tests for Enterprise Neural Phase 2 Step 1 — the `governance/crypto/`
package: `KeyId`/`KeyPurpose`/`KeyStatus` vocabulary, the `KeyProvider`
Protocol's one production-capable implementation
(`LocalEnvelopeKeyProvider`), and the self-describing encrypted
envelope format. Covers the non-negotiable Phase 2 misuse-test list
from `docs/enterprise-neural/02_PHASE2_DESIGN.md` Sec 4, to the extent
testable at this package's own boundary (call-site/DB-level tests for
cross-tenant isolation through application interfaces are a later
step, once `db/encryption.py` etc. are wired onto this provider).
"""

from __future__ import annotations

import inspect
import os

import pytest
from hypothesis import given
from hypothesis import strategies as st

from responsibleai.governance.crypto import (
    DecryptionError,
    EnvelopeFormatError,
    InMemoryWrappedKeyStore,
    KeyId,
    KeyNotFoundError,
    KeyPurpose,
    KeyRevokedError,
    KeyStatus,
    LocalEnvelopeKeyProvider,
    decode_envelope,
    decrypt_envelope,
    encode_envelope,
    encrypt_envelope,
)


def _provider(environment: str = "test") -> LocalEnvelopeKeyProvider:
    return LocalEnvelopeKeyProvider(os.urandom(32), environment=environment)


class TestKeyId:
    def test_round_trips_through_string(self) -> None:
        key_id = KeyId(
            purpose=KeyPurpose.FIELD_ENCRYPTION, tenant_id="org1", version=3, environment="prod"
        )
        assert KeyId.from_string(key_id.to_string()) == key_id

    def test_none_tenant_round_trips(self) -> None:
        key_id = KeyId(
            purpose=KeyPurpose.AUDIT_ANCHOR, tenant_id=None, version=1, environment="prod"
        )
        assert KeyId.from_string(key_id.to_string()).tenant_id is None

    def test_rejects_version_below_one(self) -> None:
        with pytest.raises(ValueError, match="version"):
            KeyId(
                purpose=KeyPurpose.FIELD_ENCRYPTION, tenant_id=None, version=0, environment="prod"
            )

    def test_rejects_empty_environment(self) -> None:
        with pytest.raises(ValueError, match="environment"):
            KeyId(purpose=KeyPurpose.FIELD_ENCRYPTION, tenant_id=None, version=1, environment="")

    def test_rejects_colon_in_tenant_id(self) -> None:
        with pytest.raises(ValueError, match="tenant_id"):
            KeyId(
                purpose=KeyPurpose.FIELD_ENCRYPTION,
                tenant_id="org:1",
                version=1,
                environment="prod",
            )

    def test_rejects_empty_string_tenant_id(self) -> None:
        """Found by the round-trip property test below: `""` collides
        with the wire encoding used for `None` -- a caller meaning "no
        tenant" must pass `None`, never an empty string."""
        with pytest.raises(ValueError, match="tenant_id"):
            KeyId(purpose=KeyPurpose.FIELD_ENCRYPTION, tenant_id="", version=1, environment="prod")

    def test_rejects_nul_byte_in_tenant_id(self) -> None:
        """Found by the round-trip property test below: a NUL byte in
        tenant_id collides with the envelope format's own field
        separator (`governance/crypto/envelope.py`)."""
        with pytest.raises(ValueError, match="tenant_id"):
            KeyId(
                purpose=KeyPurpose.FIELD_ENCRYPTION,
                tenant_id="org\x00evil",
                version=1,
                environment="prod",
            )

    def test_a_real_tenant_id_of_a_single_hyphen_round_trips_correctly(self) -> None:
        """Regression guard: an earlier encoding used `"-"` as the
        `None` sentinel, which collided with a literal tenant named
        `"-"`. The fix uses `""` (rejected as a valid tenant_id above)
        instead, so `"-"` is just an ordinary tenant_id value now."""
        key_id = KeyId(
            purpose=KeyPurpose.FIELD_ENCRYPTION, tenant_id="-", version=1, environment="prod"
        )
        assert KeyId.from_string(key_id.to_string()).tenant_id == "-"

    def test_from_string_rejects_malformed_input(self) -> None:
        with pytest.raises(ValueError):
            KeyId.from_string("not-a-valid-key-id")

    def test_from_string_rejects_non_numeric_version(self) -> None:
        with pytest.raises(ValueError, match="Malformed"):
            KeyId.from_string("prod:field_encryption:org1:not-a-number")

    def test_rejects_colon_in_environment(self) -> None:
        with pytest.raises(ValueError, match="environment"):
            KeyId(
                purpose=KeyPurpose.FIELD_ENCRYPTION, tenant_id=None, version=1, environment="p:rod"
            )

    def test_rejects_nul_byte_in_environment(self) -> None:
        with pytest.raises(ValueError, match="environment"):
            KeyId(
                purpose=KeyPurpose.FIELD_ENCRYPTION,
                tenant_id=None,
                version=1,
                environment="p\x00rod",
            )

    def test_aad_is_deterministic_for_same_fields(self) -> None:
        a = KeyId(purpose=KeyPurpose.WEBHOOK_SIGNING, tenant_id="t", version=1, environment="e")
        b = KeyId(purpose=KeyPurpose.WEBHOOK_SIGNING, tenant_id="t", version=1, environment="e")
        assert a.to_aad() == b.to_aad()

    def test_aad_differs_when_any_field_differs(self) -> None:
        base = KeyId(purpose=KeyPurpose.WEBHOOK_SIGNING, tenant_id="t", version=1, environment="e")
        variants = [
            KeyId(purpose=KeyPurpose.SESSION_SIGNING, tenant_id="t", version=1, environment="e"),
            KeyId(
                purpose=KeyPurpose.WEBHOOK_SIGNING, tenant_id="other", version=1, environment="e"
            ),
            KeyId(purpose=KeyPurpose.WEBHOOK_SIGNING, tenant_id="t", version=2, environment="e"),
            KeyId(purpose=KeyPurpose.WEBHOOK_SIGNING, tenant_id="t", version=1, environment="e2"),
        ]
        for v in variants:
            assert v.to_aad() != base.to_aad()


class TestLocalEnvelopeKeyProviderConstruction:
    def test_rejects_wrong_root_key_length(self) -> None:
        with pytest.raises(ValueError, match="32 bytes"):
            LocalEnvelopeKeyProvider(os.urandom(16), environment="test")

    def test_rejects_empty_environment(self) -> None:
        with pytest.raises(ValueError, match="environment"):
            LocalEnvelopeKeyProvider(os.urandom(32), environment="")


class TestGetEncryptionKey:
    async def test_first_use_generates_version_one(self) -> None:
        provider = _provider()
        key_id, dek = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        assert key_id.version == 1
        assert len(dek) == 32

    async def test_repeated_calls_return_the_same_current_key(self) -> None:
        provider = _provider()
        key_id_a, dek_a = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        key_id_b, dek_b = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        assert key_id_a == key_id_b
        assert dek_a == dek_b

    async def test_different_tenants_get_different_keys(self) -> None:
        provider = _provider()
        _, dek_a = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        _, dek_b = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org2")
        assert dek_a != dek_b

    async def test_different_purposes_get_different_keys(self) -> None:
        provider = _provider()
        _, dek_a = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        _, dek_b = await provider.get_encryption_key(KeyPurpose.WEBHOOK_SIGNING, "org1")
        assert dek_a != dek_b


class TestRotation:
    async def test_rotate_produces_next_version(self) -> None:
        provider = _provider()
        await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        new_key_id = await provider.rotate(KeyPurpose.FIELD_ENCRYPTION, "org1")
        assert new_key_id.version == 2

    async def test_new_writes_use_the_rotated_version(self) -> None:
        provider = _provider()
        await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        new_key_id = await provider.rotate(KeyPurpose.FIELD_ENCRYPTION, "org1")
        current_key_id, _ = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        assert current_key_id == new_key_id

    async def test_data_encrypted_before_rotation_remains_readable(self) -> None:
        provider = _provider()
        old_key_id, old_dek = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        await provider.rotate(KeyPurpose.FIELD_ENCRYPTION, "org1")
        # Old (now retired) key is still resolvable -- policy per design doc Sec 3.4/3.6.
        resolved = await provider.get_decryption_key(old_key_id)
        assert resolved == old_dek

    async def test_rotate_with_no_existing_key_starts_at_version_one(self) -> None:
        provider = _provider()
        key_id = await provider.rotate(KeyPurpose.SESSION_SIGNING, None)
        assert key_id.version == 1

    async def test_retire_stops_new_writes_but_keeps_data_readable(self) -> None:
        provider = _provider()
        key_id, dek = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        await provider.retire(key_id)
        # No longer the current key -- a fresh call generates a new version.
        new_key_id, _ = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        assert new_key_id.version == 2
        # But the retired key is still resolvable for old data.
        resolved = await provider.get_decryption_key(key_id)
        assert resolved == dek


class TestWrappedKeyCorruption:
    """White-box tests reaching into the `WrappedKeyStore` directly to
    simulate storage-layer corruption of the *wrapped DEK itself*
    (distinct from envelope-level ciphertext corruption, tested above)
    -- e.g. a bit-flip in the `crypto_keys` table's wrapped-key column
    once that persistence layer exists."""

    async def test_corrupted_wrapped_dek_is_rejected_on_unwrap(self) -> None:
        store = InMemoryWrappedKeyStore()
        provider = LocalEnvelopeKeyProvider(os.urandom(32), environment="test", store=store)
        key_id, _ = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        record = await store.get(key_id)
        assert record is not None
        corrupted_wrapped = bytearray(record.wrapped_dek)
        corrupted_wrapped[-1] ^= 0xFF
        await store.put(
            record.__class__(
                key_id=key_id, wrapped_dek=bytes(corrupted_wrapped), status=record.status
            )
        )
        with pytest.raises(DecryptionError):
            await provider.get_decryption_key(key_id)

    async def test_truncated_wrapped_dek_is_rejected(self) -> None:
        store = InMemoryWrappedKeyStore()
        provider = LocalEnvelopeKeyProvider(os.urandom(32), environment="test", store=store)
        key_id, _ = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        record = await store.get(key_id)
        assert record is not None
        await store.put(
            record.__class__(key_id=key_id, wrapped_dek=b"too short", status=record.status)
        )
        with pytest.raises(DecryptionError, match="nonce"):
            await provider.get_decryption_key(key_id)


class TestRevocationAndNotFound:
    async def test_revoked_key_cannot_be_used_for_decryption(self) -> None:
        provider = _provider()
        key_id, _ = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        await provider.revoke(key_id)
        with pytest.raises(KeyRevokedError):
            await provider.get_decryption_key(key_id)

    async def test_revoked_key_is_refused_even_though_data_predates_revocation(self) -> None:
        """Distinguishes REVOKED from RETIRED: retired data stays
        readable (see TestRotation above), revoked data never does,
        even though both cases involve a key that isn't current."""
        provider = _provider()
        key_id, dek = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        envelope = encrypt_envelope(dek, key_id, b"secret")
        await provider.revoke(key_id)
        with pytest.raises(KeyRevokedError):
            await provider.get_decryption_key(key_id)
        # The ciphertext itself still exists but is now unreachable
        # through the provider -- confirming this is a provider-level
        # refusal, not a data-loss bug.
        assert decrypt_envelope(dek, key_id, envelope) == b"secret"

    async def test_unsupported_key_version_raises_not_found(self) -> None:
        provider = _provider()
        fake = KeyId(
            purpose=KeyPurpose.FIELD_ENCRYPTION, tenant_id="org1", version=99, environment="test"
        )
        with pytest.raises(KeyNotFoundError):
            await provider.get_decryption_key(fake)

    async def test_wrong_environment_raises_not_found(self) -> None:
        provider = _provider(environment="test")
        key_id, _ = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        wrong_env = KeyId(
            purpose=key_id.purpose,
            tenant_id=key_id.tenant_id,
            version=key_id.version,
            environment="prod",
        )
        with pytest.raises(KeyNotFoundError):
            await provider.get_decryption_key(wrong_env)

    async def test_set_status_on_unknown_key_raises_not_found(self) -> None:
        store = InMemoryWrappedKeyStore()
        fake = KeyId(
            purpose=KeyPurpose.FIELD_ENCRYPTION, tenant_id="org1", version=1, environment="test"
        )
        with pytest.raises(KeyNotFoundError):
            await store.set_status(fake, KeyStatus.RETIRED)


class TestEnvelope:
    async def test_encrypt_decrypt_round_trip(self) -> None:
        provider = _provider()
        key_id, dek = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        envelope = encrypt_envelope(dek, key_id, b"the secret value")
        assert decrypt_envelope(dek, key_id, envelope) == b"the secret value"

    async def test_base64_encode_decode_round_trip(self) -> None:
        provider = _provider()
        key_id, dek = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        envelope = encrypt_envelope(dek, key_id, b"payload")
        encoded = encode_envelope(envelope)
        assert isinstance(encoded, str)
        assert decode_envelope(encoded) == envelope

    async def test_corrupted_ciphertext_is_rejected(self) -> None:
        provider = _provider()
        key_id, dek = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        envelope = bytearray(encrypt_envelope(dek, key_id, b"payload"))
        envelope[-1] ^= 0xFF
        with pytest.raises(DecryptionError):
            decrypt_envelope(dek, key_id, bytes(envelope))

    async def test_tampered_embedded_key_id_is_rejected(self) -> None:
        provider = _provider()
        key_id, dek = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        envelope = encrypt_envelope(dek, key_id, b"payload")
        tampered_key_id = KeyId(
            purpose=key_id.purpose,
            tenant_id=key_id.tenant_id,
            version=key_id.version + 1,
            environment=key_id.environment,
        )
        _, rest = envelope.split(b"\x00", 1)
        tampered = tampered_key_id.to_string().encode() + b"\x00" + rest
        with pytest.raises((DecryptionError, EnvelopeFormatError)):
            decrypt_envelope(dek, key_id, tampered)

    def test_malformed_envelope_missing_separator_is_rejected(self) -> None:
        with pytest.raises(EnvelopeFormatError):
            decrypt_envelope(
                os.urandom(32),
                KeyId(
                    purpose=KeyPurpose.FIELD_ENCRYPTION, tenant_id=None, version=1, environment="e"
                ),
                b"no separator at all",
            )

    def test_malformed_envelope_truncated_nonce_is_rejected(self) -> None:
        key_id = KeyId(
            purpose=KeyPurpose.FIELD_ENCRYPTION, tenant_id=None, version=1, environment="e"
        )
        malformed = key_id.to_string().encode() + b"\x00" + b"short"
        with pytest.raises(EnvelopeFormatError):
            decrypt_envelope(os.urandom(32), key_id, malformed)

    def test_malformed_envelope_invalid_utf8_key_id_prefix_is_rejected(self) -> None:
        key_id = KeyId(
            purpose=KeyPurpose.FIELD_ENCRYPTION, tenant_id=None, version=1, environment="e"
        )
        malformed = b"\xff\xfe not valid utf-8" + b"\x00" + os.urandom(12) + b"rest"
        with pytest.raises(EnvelopeFormatError):
            decrypt_envelope(os.urandom(32), key_id, malformed)

    def test_decode_envelope_rejects_invalid_base64(self) -> None:
        with pytest.raises(EnvelopeFormatError):
            decode_envelope("not valid base64 !!! ###")

    def test_decode_envelope_rejects_plaintext_a_lenient_decoder_would_silently_accept(
        self,
    ) -> None:
        """Regression guard: `base64.urlsafe_b64decode` alone defaults
        to `validate=False`, which silently discards invalid
        characters instead of raising -- so a plaintext string like an
        IP address ("203.0.113.5") "successfully" decodes to
        meaningless bytes rather than being rejected. Found during
        Enterprise Neural Phase 2 Step 3's `db/encryption.py` wiring,
        where this exact leniency let plaintext fall through to the
        decrypt path. `decode_envelope` must reject it strictly."""
        with pytest.raises(EnvelopeFormatError):
            decode_envelope("203.0.113.5")

    async def test_wrong_key_id_expectation_is_rejected(self) -> None:
        """A caller that resolved the wrong purpose/tenant DEK for the
        envelope it's decrypting is caught by the embedded-KeyId check,
        the concrete form of "wrong-purpose key" / "wrong tenant key"
        at this package's boundary."""
        provider = _provider()
        key_id_a, dek_a = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        key_id_b, _ = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org2")
        envelope = encrypt_envelope(dek_a, key_id_a, b"payload")
        with pytest.raises(DecryptionError):
            decrypt_envelope(dek_a, key_id_b, envelope)

    async def test_cross_tenant_decryption_fails_even_with_correct_dek_for_wrong_tenant(
        self,
    ) -> None:
        provider = _provider()
        key_id_a, dek_a = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        key_id_b, dek_b = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org2")
        envelope = encrypt_envelope(dek_a, key_id_a, b"org1 secret")
        # Attempting to read org1's envelope using org2's own (correctly
        # resolved) key and expected id fails at the KeyId-match check.
        with pytest.raises(DecryptionError):
            decrypt_envelope(dek_b, key_id_b, envelope)

    def test_public_api_has_no_nonce_parameter(self) -> None:
        """Structural guarantee: nonce misuse cannot occur through the
        public API because there is no parameter to misuse it with."""
        sig = inspect.signature(encrypt_envelope)
        assert "nonce" not in sig.parameters


class TestNoSecretLeakageInErrors:
    async def test_key_not_found_error_message_never_contains_key_material(self) -> None:
        provider = _provider()
        key_id, dek = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        fake = KeyId(
            purpose=key_id.purpose, tenant_id=key_id.tenant_id, version=999, environment="test"
        )
        try:
            await provider.get_decryption_key(fake)
        except KeyNotFoundError as exc:
            assert dek.hex() not in str(exc)
            assert dek not in str(exc).encode(errors="ignore")

    async def test_decryption_error_message_never_contains_key_material(self) -> None:
        provider = _provider()
        key_id, dek = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        envelope = bytearray(encrypt_envelope(dek, key_id, b"payload"))
        envelope[-1] ^= 0xFF
        try:
            decrypt_envelope(dek, key_id, bytes(envelope))
        except DecryptionError as exc:
            assert dek.hex() not in str(exc)


class TestProperties:
    @given(
        purpose=st.sampled_from(list(KeyPurpose)),
        tenant_id=st.one_of(
            st.none(),
            st.text(min_size=1, max_size=20).filter(lambda t: ":" not in t and "\x00" not in t),
        ),
        plaintext=st.binary(min_size=0, max_size=200),
    )
    def test_encrypt_decrypt_round_trips_for_arbitrary_purpose_tenant_plaintext(
        self, purpose: KeyPurpose, tenant_id: str | None, plaintext: bytes
    ) -> None:
        import asyncio

        async def run() -> None:
            provider = _provider()
            key_id, dek = await provider.get_encryption_key(purpose, tenant_id)
            envelope = encrypt_envelope(dek, key_id, plaintext)
            assert decrypt_envelope(dek, key_id, envelope) == plaintext

        asyncio.run(run())

    @given(rotations=st.integers(min_value=1, max_value=8))
    def test_rotation_versions_are_strictly_monotonic(self, rotations: int) -> None:
        import asyncio

        async def run() -> None:
            provider = _provider()
            versions = []
            for _ in range(rotations):
                key_id = await provider.rotate(KeyPurpose.FIELD_ENCRYPTION, "org1")
                versions.append(key_id.version)
            assert versions == sorted(versions)
            assert len(set(versions)) == len(versions)

        asyncio.run(run())
