# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for opt-in field-level encryption (db/encryption.py) and its
application to audit_log.ip_address."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from cryptography.fernet import Fernet, MultiFernet

from responsibleai.db.audit_repository import AuditRepository
from responsibleai.db.encryption import SENSITIVE_ENCRYPTED_COLUMNS, EncryptedString, _load_fernet
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

    def test_whitepact_env_var_is_honored(self, monkeypatch):
        monkeypatch.delenv("RAI_FIELD_ENCRYPTION_KEY", raising=False)
        key = Fernet.generate_key().decode()
        monkeypatch.setenv("WHITEPACT_FIELD_ENCRYPTION_KEY", key)
        assert _load_fernet() is not None

    def test_conflicting_keys_fail_loudly(self, monkeypatch):
        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()
        monkeypatch.setenv("WHITEPACT_FIELD_ENCRYPTION_KEY", key1)
        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", key2)
        with pytest.raises(ValueError, match="Conflicting.*field encryption"):
            _load_fernet()

    def test_matching_keys_succeed(self, monkeypatch):
        key = Fernet.generate_key().decode()
        monkeypatch.setenv("WHITEPACT_FIELD_ENCRYPTION_KEY", key)
        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", key)
        assert _load_fernet() is not None


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

    def test_pre_encryption_plaintext_fails_closed_when_key_enabled(self, monkeypatch):
        monkeypatch.delenv("RAI_FIELD_ENCRYPTION_KEY", raising=False)
        monkeypatch.delenv("WHITEPACT_ALLOW_LEGACY_PLAINTEXT", raising=False)
        monkeypatch.delenv("WHITEPACT_ENV", raising=False)
        col = EncryptedString()
        stored = col.process_bind_param("203.0.113.5", _FAKE_TYPE_PARAMS)

        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
        from responsibleai.db.encryption import FieldEncryptionError

        with pytest.raises(FieldEncryptionError, match="Unrecognized encrypted field format"):
            col.process_result_value(stored, _FAKE_TYPE_PARAMS)

    def test_explicit_legacy_plaintext_allowed_only_when_flagged(self, monkeypatch):
        from responsibleai.db.encryption import _LEGACY_PLAINTEXT, FieldEncryptionError

        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
        monkeypatch.delenv("WHITEPACT_ALLOW_LEGACY_PLAINTEXT", raising=False)
        col = EncryptedString()
        with pytest.raises(FieldEncryptionError):
            col.process_result_value(f"{_LEGACY_PLAINTEXT}203.0.113.5", _FAKE_TYPE_PARAMS)
        monkeypatch.setenv("WHITEPACT_ALLOW_LEGACY_PLAINTEXT", "1")
        assert (
            col.process_result_value(f"{_LEGACY_PLAINTEXT}203.0.113.5", _FAKE_TYPE_PARAMS)
            == "203.0.113.5"
        )

    def test_corrupt_ciphertext_and_wrong_key_fail_closed(self, monkeypatch):
        from responsibleai.db.encryption import FieldEncryptionError

        key = Fernet.generate_key().decode()
        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", key)
        col = EncryptedString()
        ciphertext = col.process_bind_param("secret-value", _FAKE_TYPE_PARAMS)
        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
        with pytest.raises(FieldEncryptionError, match="Ciphertext authentication failed"):
            col.process_result_value(ciphertext, _FAKE_TYPE_PARAMS)
        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", key)
        with pytest.raises(FieldEncryptionError):
            col.process_result_value("wpenc:v1:not-a-token", _FAKE_TYPE_PARAMS)
        monkeypatch.setenv("WHITEPACT_ENV", "production")
        with pytest.raises(FieldEncryptionError):
            col.process_result_value("not-ciphertext", _FAKE_TYPE_PARAMS)


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


def test_sensitive_encrypted_column_inventory_includes_launch_critical_secrets() -> None:
    tables = {table for table, _column in SENSITIVE_ENCRYPTED_COLUMNS}
    assert "org_api_keys" in tables
    assert "webhook_configs" in tables
    assert "governance_approvals" in tables
    assert "upstream_mcp_servers" in tables
