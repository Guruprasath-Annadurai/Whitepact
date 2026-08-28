"""Tests for Security Remediation Gap 1 —
`db/crypto_activation.py`'s `activate_production_crypto()`.

Reproduces the documented finding first (crypto foundation dormant by
default), then verifies the activation module's own fail-closed
behavior. The underlying crypto primitives (wrong-key/wrong-tenant/
wrong-purpose/revoked-key/unknown-version/metadata-tampering
rejection, AEAD-AAD binding) are already covered by
`tests/test_governance_crypto.py` and `tests/test_crypto_key_repository.py`
— this file tests the activation *wiring* specifically: what happens
when a deployment does or doesn't set `enterprise_mode`/`crypto_root_key`,
and that once activated, the full `EncryptedString` path actually uses
real encryption end-to-end, not just the underlying primitives in
isolation.
"""

from __future__ import annotations

import logging
import secrets

import pytest

from responsibleai.dashboard.config import Settings
from responsibleai.db import encryption as encryption_module
from responsibleai.db.crypto_activation import CryptoActivationError, activate_production_crypto
from responsibleai.db.encryption import (
    _get_active_field_encryption_key,
    clear_field_encryption_key,
)
from responsibleai.db.engine import DatabaseEngine, create_engine
from responsibleai.governance.crypto import DecryptionError, encode_envelope, encrypt_envelope
from responsibleai.governance.crypto.types import KeyPurpose


def _valid_root_key_hex() -> str:
    return secrets.token_hex(32)


async def _engine() -> DatabaseEngine:
    engine = create_engine(":memory:")
    await engine.init()
    return engine


@pytest.fixture(autouse=True)
def _reset_active_keys():
    """Every test starts and ends with no active key configured --
    module-level state in db/encryption.py and auth/saml.py must not
    leak between tests."""
    clear_field_encryption_key()
    yield
    clear_field_encryption_key()


class TestReproduceTheDormancyFinding:
    """Before testing the fix, confirm the documented gap is real."""

    async def test_default_settings_have_enterprise_mode_off(self) -> None:
        settings = Settings()
        assert settings.enterprise_mode is False

    async def test_no_activation_call_means_no_active_key(self) -> None:
        assert _get_active_field_encryption_key() is None


class TestFailClosedActivation:
    async def test_enterprise_mode_false_is_a_no_op(self) -> None:
        settings = Settings(enterprise_mode=False)
        engine = await _engine()
        await activate_production_crypto(settings, engine)
        assert _get_active_field_encryption_key() is None
        await engine.close()

    async def test_enterprise_mode_true_without_root_key_raises(self) -> None:
        settings = Settings(enterprise_mode=True, crypto_root_key=None)
        engine = await _engine()
        with pytest.raises(CryptoActivationError, match="crypto_root_key"):
            await activate_production_crypto(settings, engine)
        # Fail closed means no partial activation either.
        assert _get_active_field_encryption_key() is None
        await engine.close()

    async def test_enterprise_mode_true_with_malformed_hex_raises(self) -> None:
        settings = Settings(enterprise_mode=True, crypto_root_key="not-valid-hex!!")
        engine = await _engine()
        with pytest.raises(CryptoActivationError, match="hex"):
            await activate_production_crypto(settings, engine)
        await engine.close()

    async def test_enterprise_mode_true_with_wrong_length_key_raises(self) -> None:
        settings = Settings(enterprise_mode=True, crypto_root_key=secrets.token_hex(16))
        engine = await _engine()
        with pytest.raises(CryptoActivationError, match="32 bytes"):
            await activate_production_crypto(settings, engine)
        await engine.close()

    async def test_valid_activation_configures_field_encryption_key(self) -> None:
        settings = Settings(enterprise_mode=True, crypto_root_key=_valid_root_key_hex())
        engine = await _engine()
        await activate_production_crypto(settings, engine)
        active = _get_active_field_encryption_key()
        assert active is not None
        key_id, dek = active
        assert key_id.purpose is KeyPurpose.FIELD_ENCRYPTION
        assert len(dek) == 32
        await engine.close()


class TestActivatedEncryptionRoundTrips:
    """Once activated, the real EncryptedString column path must use
    envelope encryption end-to-end, not just the primitives."""

    async def test_field_write_and_read_round_trips_through_real_encryption(self) -> None:
        settings = Settings(enterprise_mode=True, crypto_root_key=_valid_root_key_hex())
        engine = await _engine()
        await activate_production_crypto(settings, engine)

        col = encryption_module.EncryptedString()
        stored = col.process_bind_param("a secret value", dialect=None)
        assert stored is not None
        assert stored != "a secret value"  # not plaintext
        assert stored.startswith(encryption_module._NEW_SCHEME_PREFIX)

        recovered = col.process_result_value(stored, dialect=None)
        assert recovered == "a secret value"
        await engine.close()

    async def test_enterprise_mode_never_silently_stores_plaintext(self) -> None:
        """The specific property the directive names: enterprise mode
        must not silently degrade to plaintext even if something about
        the environment looks like it would (e.g. no legacy
        RAI_FIELD_ENCRYPTION_KEY set)."""
        settings = Settings(enterprise_mode=True, crypto_root_key=_valid_root_key_hex())
        engine = await _engine()
        await activate_production_crypto(settings, engine)

        col = encryption_module.EncryptedString()
        stored = col.process_bind_param("plan:enterprise:no-plaintext", dialect=None)
        assert "plan:enterprise:no-plaintext" not in (stored or "")
        await engine.close()


class TestCorruptedAndTamperedCiphertextRejected:
    async def test_corrupted_new_scheme_ciphertext_is_rejected(self) -> None:
        settings = Settings(enterprise_mode=True, crypto_root_key=_valid_root_key_hex())
        engine = await _engine()
        await activate_production_crypto(settings, engine)

        col = encryption_module.EncryptedString()
        stored = col.process_bind_param("secret", dialect=None)
        assert stored is not None
        corrupted = stored[:-4] + ("0" if stored[-1] != "0" else "1") + stored[-3:]

        with pytest.raises(Exception):  # noqa: B017,PT011 -- AEAD tag failure or decode error, either proves rejection
            col.process_result_value(corrupted, dialect=None)
        await engine.close()

    async def test_new_scheme_prefix_with_no_active_key_fails_closed(self) -> None:
        """A value that claims the new-scheme format but is read back
        with no key configured must raise, never fall through to
        legacy/plaintext interpretation -- see db/encryption.py's own
        documented reasoning."""
        settings = Settings(enterprise_mode=True, crypto_root_key=_valid_root_key_hex())
        engine = await _engine()
        await activate_production_crypto(settings, engine)
        col = encryption_module.EncryptedString()
        stored = col.process_bind_param("secret", dialect=None)
        assert stored is not None

        clear_field_encryption_key()  # simulate key becoming unavailable
        with pytest.raises(DecryptionError):
            col.process_result_value(stored, dialect=None)
        await engine.close()


class TestRotationAndKeyVersioning:
    async def test_rotated_key_reads_old_ciphertext_and_writes_under_new_version(self) -> None:
        from responsibleai.db.crypto_key_repository import CryptoKeyRepository
        from responsibleai.governance.crypto import LocalEnvelopeKeyProvider

        engine = await _engine()
        root_key = secrets.token_bytes(32)
        store = CryptoKeyRepository(engine)
        provider = LocalEnvelopeKeyProvider(
            root_key=root_key, environment="production", store=store
        )

        key_id_v1, dek_v1 = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, None)
        assert key_id_v1.version == 1
        envelope = encrypt_envelope(dek_v1, key_id_v1, b"old data")
        old_ciphertext = encode_envelope(envelope)

        new_key_id = await provider.rotate(KeyPurpose.FIELD_ENCRYPTION, None)
        assert new_key_id.version == 2

        # Old ciphertext (v1) must still be decryptable after rotation.
        dek_for_old = await provider.get_decryption_key(key_id_v1)
        from responsibleai.governance.crypto import decode_envelope, decrypt_envelope

        recovered = decrypt_envelope(dek_for_old, key_id_v1, decode_envelope(old_ciphertext))
        assert recovered == b"old data"

        # New encryption uses the rotated (v2) key.
        key_id_new, _dek_new = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, None)
        assert key_id_new.version == 2
        await engine.close()


class TestSecretsNeverAppearInLogs:
    async def test_activation_log_output_never_contains_root_key_or_dek(self, caplog) -> None:
        root_key_hex = _valid_root_key_hex()
        settings = Settings(enterprise_mode=True, crypto_root_key=root_key_hex)
        engine = await _engine()

        with caplog.at_level(logging.DEBUG):
            await activate_production_crypto(settings, engine)

        active = _get_active_field_encryption_key()
        assert active is not None
        _key_id, dek = active
        dek_hex = dek.hex()

        log_text = "\n".join(record.getMessage() for record in caplog.records)
        assert root_key_hex not in log_text
        assert dek_hex not in log_text
        await engine.close()
