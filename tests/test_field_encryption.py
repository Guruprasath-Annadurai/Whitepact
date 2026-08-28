"""Tests for opt-in field-level encryption (db/encryption.py) and its
application to audit_log.ip_address.

Also covers Enterprise Neural Phase 2 Step 3's dual-scheme wiring: the
new `governance/crypto`-based scheme (`configure_field_encryption_key`)
coexisting with the legacy `RAI_FIELD_ENCRYPTION_KEY`-based Fernet
scheme, format detection between them, and fail-closed behavior for
the new scheme specifically (see `db/encryption.py`'s module
docstring for why the two schemes have different failure postures).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from cryptography.fernet import Fernet, MultiFernet

from responsibleai.db.audit_repository import AuditRepository
from responsibleai.db.encryption import (
    EncryptedString,
    _load_fernet,
    clear_field_encryption_key,
    configure_field_encryption_key,
)
from responsibleai.db.engine import create_engine
from responsibleai.governance.crypto import DecryptionError, KeyId, KeyPurpose
from responsibleai.rbac.models import AuditEntry

_FAKE_TYPE_PARAMS = None  # dialect argument is unused by EncryptedString


@pytest.fixture(autouse=True)
def _reset_field_encryption_key():
    """`_active_field_encryption_key` is process-global state in
    db/encryption.py -- reset it around every test in this module so
    the new-scheme tests below can't leak into the legacy-only tests
    above (or into other test files importing this module)."""
    clear_field_encryption_key()
    yield
    clear_field_encryption_key()


def _field_encryption_key_id(version: int = 1) -> KeyId:
    return KeyId(
        purpose=KeyPurpose.FIELD_ENCRYPTION, tenant_id=None, version=version, environment="test"
    )


class TestLoadFernet:
    def test_returns_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("RAI_FIELD_ENCRYPTION_KEY", raising=False)
        assert _load_fernet() is None

    def test_returns_fernet_when_set(self, monkeypatch):
        key = Fernet.generate_key().decode()
        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", key)
        assert _load_fernet() is not None

    def test_raises_on_malformed_key(self, monkeypatch):
        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", "not-a-valid-fernet-key")
        with pytest.raises(ValueError, match="invalid Fernet key"):
            _load_fernet()

    def test_multiple_keys_returns_multifernet(self, monkeypatch):
        keys = f"{Fernet.generate_key().decode()},{Fernet.generate_key().decode()}"
        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", keys)
        fernet = _load_fernet()
        assert isinstance(fernet, MultiFernet)

    def test_only_commas_and_whitespace_is_treated_as_unset(self, monkeypatch):
        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", " , , ")
        assert _load_fernet() is None

    def test_rotation_new_key_first_still_decrypts_old_ciphertext(self, monkeypatch):
        old_key = Fernet.generate_key().decode()
        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", old_key)
        col = EncryptedString()
        ciphertext = col.process_bind_param("203.0.113.5", _FAKE_TYPE_PARAMS)

        new_key = Fernet.generate_key().decode()
        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", f"{new_key},{old_key}")
        assert col.process_result_value(ciphertext, _FAKE_TYPE_PARAMS) == "203.0.113.5"

        # New writes after rotation use the new (first) key.
        new_ciphertext = col.process_bind_param("203.0.113.5", _FAKE_TYPE_PARAMS)
        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", new_key)
        assert col.process_result_value(new_ciphertext, _FAKE_TYPE_PARAMS) == "203.0.113.5"


class TestEncryptedStringTypeDecorator:
    def test_passthrough_when_key_unset(self, monkeypatch):
        monkeypatch.delenv("RAI_FIELD_ENCRYPTION_KEY", raising=False)
        col = EncryptedString()
        bound = col.process_bind_param("203.0.113.5", _FAKE_TYPE_PARAMS)
        assert bound == "203.0.113.5"
        assert col.process_result_value(bound, _FAKE_TYPE_PARAMS) == "203.0.113.5"

    def test_none_passes_through_regardless_of_key(self, monkeypatch):
        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
        col = EncryptedString()
        assert col.process_bind_param(None, _FAKE_TYPE_PARAMS) is None
        assert col.process_result_value(None, _FAKE_TYPE_PARAMS) is None

    def test_round_trips_when_key_set(self, monkeypatch):
        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
        col = EncryptedString()
        ciphertext = col.process_bind_param("203.0.113.5", _FAKE_TYPE_PARAMS)
        assert ciphertext != "203.0.113.5"  # actually encrypted, not a no-op
        assert col.process_result_value(ciphertext, _FAKE_TYPE_PARAMS) == "203.0.113.5"

    def test_pre_encryption_plaintext_survives_key_being_enabled_later(self, monkeypatch):
        """A value written before the key was ever set (plaintext in the DB)
        must still be readable once encryption is turned on, rather than
        crashing the request with an InvalidToken error."""
        monkeypatch.delenv("RAI_FIELD_ENCRYPTION_KEY", raising=False)
        col = EncryptedString()
        stored = col.process_bind_param("203.0.113.5", _FAKE_TYPE_PARAMS)

        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
        assert col.process_result_value(stored, _FAKE_TYPE_PARAMS) == "203.0.113.5"


class TestAuditLogIpAddressEncryption:
    @pytest.fixture()
    async def db(self):
        engine = create_engine(":memory:")
        await engine.init()
        yield engine
        await engine.close()

    async def test_ip_address_round_trips_and_hash_chain_still_verifies(self, db, monkeypatch):
        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
        repo = AuditRepository(db)
        entry = AuditEntry(
            endpoint="/api/evaluate",
            method="POST",
            status_code=200,
            ip_address="203.0.113.5",
            timestamp=datetime.now(UTC).isoformat(),
        )
        await repo.write(entry)

        rows = await repo.query(limit=10)
        assert rows[0]["ip_address"] == "203.0.113.5"

        # ip_address is never part of the hash-chain material, so encrypting
        # it must have zero effect on chain integrity.
        result = await repo.verify_chain()
        assert result["intact"] is True


class TestConfigureFieldEncryptionKey:
    def test_rejects_wrong_purpose(self):
        wrong_purpose_key_id = KeyId(
            purpose=KeyPurpose.WEBHOOK_SIGNING, tenant_id=None, version=1, environment="test"
        )
        with pytest.raises(ValueError, match="FIELD_ENCRYPTION"):
            configure_field_encryption_key(wrong_purpose_key_id, os.urandom(32))

    def test_clear_reverts_to_legacy_only_path(self, monkeypatch):
        monkeypatch.delenv("RAI_FIELD_ENCRYPTION_KEY", raising=False)
        configure_field_encryption_key(_field_encryption_key_id(), os.urandom(32))
        col = EncryptedString()
        bound = col.process_bind_param("203.0.113.5", _FAKE_TYPE_PARAMS)
        assert bound != "203.0.113.5"  # new scheme active

        clear_field_encryption_key()
        bound_after_clear = col.process_bind_param("203.0.113.5", _FAKE_TYPE_PARAMS)
        assert bound_after_clear == "203.0.113.5"  # back to plaintext passthrough


class TestNewSchemeEncryptedString:
    def test_round_trips_when_new_scheme_configured(self, monkeypatch):
        monkeypatch.delenv("RAI_FIELD_ENCRYPTION_KEY", raising=False)
        configure_field_encryption_key(_field_encryption_key_id(), os.urandom(32))
        col = EncryptedString()
        ciphertext = col.process_bind_param("203.0.113.5", _FAKE_TYPE_PARAMS)
        assert ciphertext != "203.0.113.5"
        assert col.process_result_value(ciphertext, _FAKE_TYPE_PARAMS) == "203.0.113.5"

    def test_new_scheme_takes_priority_over_legacy_for_new_writes(self, monkeypatch):
        """Once the new scheme is configured, new writes always use it
        -- there's no dial to keep writing legacy Fernet alongside it."""
        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
        configure_field_encryption_key(_field_encryption_key_id(), os.urandom(32))
        col = EncryptedString()
        bound = col.process_bind_param("203.0.113.5", _FAKE_TYPE_PARAMS)
        assert bound.startswith("wpcrypto2:")

    def test_base32_totp_secret_plaintext_is_never_misidentified_as_new_scheme_ciphertext(
        self, monkeypatch
    ):
        """Regression guard for the actual bug found wiring this up:
        base32 TOTP secrets (`pyotp.random_base32()`) use an alphabet
        that is a strict subset of base64's, at a block-aligned length,
        so a naive "does this decode as base64" format check
        misidentified genuine plaintext TOTP secrets as new-scheme
        ciphertext and raised DecryptionError trying to decrypt them.
        Format detection must use the explicit prefix, not a base64
        decodability guess."""
        monkeypatch.delenv("RAI_FIELD_ENCRYPTION_KEY", raising=False)
        col = EncryptedString()
        totp_secret = "JBSWY3DPEHPK3PXP"  # a real base32 TOTP-seed-shaped string
        bound = col.process_bind_param(totp_secret, _FAKE_TYPE_PARAMS)
        assert bound == totp_secret  # no key configured -> untouched passthrough
        assert col.process_result_value(bound, _FAKE_TYPE_PARAMS) == totp_secret

    def test_missing_key_for_new_format_value_fails_closed(self, monkeypatch):
        monkeypatch.delenv("RAI_FIELD_ENCRYPTION_KEY", raising=False)
        key_id = _field_encryption_key_id()
        dek = os.urandom(32)
        configure_field_encryption_key(key_id, dek)
        col = EncryptedString()
        ciphertext = col.process_bind_param("203.0.113.5", _FAKE_TYPE_PARAMS)

        clear_field_encryption_key()
        with pytest.raises(DecryptionError):
            col.process_result_value(ciphertext, _FAKE_TYPE_PARAMS)

    def test_tampered_new_format_ciphertext_fails_closed(self, monkeypatch):
        monkeypatch.delenv("RAI_FIELD_ENCRYPTION_KEY", raising=False)
        configure_field_encryption_key(_field_encryption_key_id(), os.urandom(32))
        col = EncryptedString()
        ciphertext = col.process_bind_param("203.0.113.5", _FAKE_TYPE_PARAMS)
        prefix, payload = ciphertext[:10], ciphertext[10:]
        assert prefix == "wpcrypto2:"
        # Flip a byte in the decoded ciphertext, not a base64 character
        # directly -- the last base64 character of a token can encode
        # unused padding bits, so mutating it doesn't always change the
        # decoded bytes at all (a flaky, not-actually-tampering test).
        import base64

        raw = bytearray(base64.urlsafe_b64decode(payload.encode()))
        raw[-1] ^= 0xFF
        tampered = prefix + base64.urlsafe_b64encode(bytes(raw)).decode()
        with pytest.raises(DecryptionError):
            col.process_result_value(tampered, _FAKE_TYPE_PARAMS)


class TestMixedSchemeCoexistence:
    """The realistic migration-window state: some rows still hold
    legacy Fernet ciphertext, some already hold new-format ciphertext,
    both readable by the same running application."""

    def test_legacy_ciphertext_still_reads_correctly_once_new_scheme_is_active(self, monkeypatch):
        legacy_key = Fernet.generate_key()
        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", legacy_key.decode())
        col = EncryptedString()
        legacy_ciphertext = col.process_bind_param("198.51.100.7", _FAKE_TYPE_PARAMS)

        configure_field_encryption_key(_field_encryption_key_id(), os.urandom(32))
        assert col.process_result_value(legacy_ciphertext, _FAKE_TYPE_PARAMS) == "198.51.100.7"

    def test_new_format_ciphertext_reads_correctly_alongside_legacy_key_still_set(
        self, monkeypatch
    ):
        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
        configure_field_encryption_key(_field_encryption_key_id(), os.urandom(32))
        col = EncryptedString()
        new_ciphertext = col.process_bind_param("203.0.113.5", _FAKE_TYPE_PARAMS)
        assert col.process_result_value(new_ciphertext, _FAKE_TYPE_PARAMS) == "203.0.113.5"

    def test_pre_encryption_plaintext_still_reads_correctly_with_new_scheme_active(
        self, monkeypatch
    ):
        """The same passthrough guarantee test_pre_encryption_plaintext_
        survives_key_being_enabled_later already covers for the legacy
        scheme, now also holding with the new scheme active."""
        monkeypatch.delenv("RAI_FIELD_ENCRYPTION_KEY", raising=False)
        col = EncryptedString()
        stored = col.process_bind_param("203.0.113.5", _FAKE_TYPE_PARAMS)  # no key at all yet

        configure_field_encryption_key(_field_encryption_key_id(), os.urandom(32))
        assert col.process_result_value(stored, _FAKE_TYPE_PARAMS) == "203.0.113.5"
