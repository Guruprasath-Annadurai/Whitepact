"""Tests for opt-in field-level encryption (db/encryption.py) and its
application to audit_log.ip_address."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from cryptography.fernet import Fernet, MultiFernet

from responsibleai.db.audit_repository import AuditRepository
from responsibleai.db.encryption import EncryptedString, _load_fernet
from responsibleai.db.engine import create_engine
from responsibleai.rbac.models import AuditEntry

_FAKE_TYPE_PARAMS = None  # dialect argument is unused by EncryptedString


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
