"""Tests for scripts/rotate_field_encryption_key.py — Enterprise
Neural Phase 2 Step 5's generalized rotation script. Covers the new
Mode 2 (migrate to/rotate within the `governance/crypto` scheme):
root-key loading/validation, the pre-flight safety check that refuses
to double-wrap unrecoverable legacy Fernet ciphertext, and an
end-to-end migration through the real `_rotate_table` sweep logic
(Mode 1's original logic, unchanged, exercised here via the new mode).
"""

from __future__ import annotations

import base64
import importlib.util
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

_SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "rotate_field_encryption_key.py"
_spec = importlib.util.spec_from_file_location("rotate_field_encryption_key", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
sys.modules["rotate_field_encryption_key"] = _module
_spec.loader.exec_module(_module)

from responsibleai.db.audit_repository import AuditRepository  # noqa: E402
from responsibleai.db.crypto_key_repository import CryptoKeyRepository  # noqa: E402
from responsibleai.db.encryption import (  # noqa: E402
    _get_active_field_encryption_key,
    clear_field_encryption_key,
)
from responsibleai.db.engine import DatabaseEngine, create_engine  # noqa: E402
from responsibleai.governance.crypto import KeyPurpose  # noqa: E402
from responsibleai.governance.crypto.local_envelope import LocalEnvelopeKeyProvider  # noqa: E402
from responsibleai.rbac.models import AuditEntry  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_field_encryption_key():
    clear_field_encryption_key()
    yield
    clear_field_encryption_key()


async def _migrated_engine() -> DatabaseEngine:
    engine = create_engine(":memory:")
    await engine.init()
    return engine


def _root_key_env(root_key: bytes) -> str:
    return base64.urlsafe_b64encode(root_key).decode()


class TestLoadRootKey:
    def test_returns_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("RAI_ROOT_KEY", raising=False)
        assert _module._load_root_key() is None

    def test_returns_bytes_when_valid(self, monkeypatch):
        root_key = os.urandom(32)
        monkeypatch.setenv("RAI_ROOT_KEY", _root_key_env(root_key))
        assert _module._load_root_key() == root_key

    def test_rejects_invalid_base64(self, monkeypatch):
        monkeypatch.setenv("RAI_ROOT_KEY", "not valid base64 !!!")
        with pytest.raises(SystemExit):
            _module._load_root_key()

    def test_rejects_wrong_length(self, monkeypatch):
        monkeypatch.setenv("RAI_ROOT_KEY", base64.urlsafe_b64encode(os.urandom(16)).decode())
        with pytest.raises(SystemExit):
            _module._load_root_key()


class TestActivateNewSchemeIfRequested:
    async def test_returns_false_when_root_key_unset(self, monkeypatch):
        monkeypatch.delenv("RAI_ROOT_KEY", raising=False)
        engine = await _migrated_engine()
        assert await _module._activate_new_scheme_if_requested(engine) is False

    async def test_activates_and_returns_true_when_set(self, monkeypatch):
        monkeypatch.setenv("RAI_ROOT_KEY", _root_key_env(os.urandom(32)))
        monkeypatch.setenv("RAI_CRYPTO_ENVIRONMENT", "test")
        engine = await _migrated_engine()
        assert await _module._activate_new_scheme_if_requested(engine) is True
        assert _get_active_field_encryption_key() is not None

    async def test_rotate_version_env_var_bumps_version(self, monkeypatch):
        root_key = os.urandom(32)
        monkeypatch.setenv("RAI_ROOT_KEY", _root_key_env(root_key))
        monkeypatch.setenv("RAI_CRYPTO_ENVIRONMENT", "test")
        engine = await _migrated_engine()
        await _module._activate_new_scheme_if_requested(engine)
        first_key_id = _get_active_field_encryption_key()[0]
        assert first_key_id.version == 1

        monkeypatch.setenv("RAI_CRYPTO_ROTATE_VERSION", "1")
        await _module._activate_new_scheme_if_requested(engine)
        second_key_id = _get_active_field_encryption_key()[0]
        assert second_key_id.version == 2


class TestRefuseIfUnrecoverableLegacyCiphertext:
    async def test_passes_when_legacy_key_available(self, monkeypatch):
        legacy_key = Fernet.generate_key()
        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", legacy_key.decode())
        engine = await _migrated_engine()
        repo = AuditRepository(engine)
        await repo.write(
            AuditEntry(
                endpoint="/x",
                method="GET",
                status_code=200,
                ip_address="203.0.113.5",
                timestamp=datetime.now(UTC).isoformat(),
            )
        )
        async with engine.raw.connect() as conn:
            await _module._refuse_if_unrecoverable_legacy_ciphertext(conn)  # must not raise

    async def test_refuses_when_legacy_ciphertext_present_without_key(self, monkeypatch):
        legacy_key = Fernet.generate_key()
        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", legacy_key.decode())
        engine = await _migrated_engine()
        repo = AuditRepository(engine)
        await repo.write(
            AuditEntry(
                endpoint="/x",
                method="GET",
                status_code=200,
                ip_address="203.0.113.5",
                timestamp=datetime.now(UTC).isoformat(),
            )
        )
        monkeypatch.delenv("RAI_FIELD_ENCRYPTION_KEY", raising=False)  # key "lost" for this run
        async with engine.raw.connect() as conn:
            with pytest.raises(SystemExit):
                await _module._refuse_if_unrecoverable_legacy_ciphertext(conn)

    async def test_passes_on_a_fresh_database_with_no_legacy_key(self, monkeypatch):
        monkeypatch.delenv("RAI_FIELD_ENCRYPTION_KEY", raising=False)
        engine = await _migrated_engine()
        async with engine.raw.connect() as conn:
            await _module._refuse_if_unrecoverable_legacy_ciphertext(conn)  # must not raise


class TestEndToEndMigration:
    async def test_migrates_legacy_ciphertext_to_new_scheme(self, monkeypatch):
        legacy_key = Fernet.generate_key()
        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", legacy_key.decode())
        engine = await _migrated_engine()
        repo = AuditRepository(engine)
        await repo.write(
            AuditEntry(
                endpoint="/x",
                method="GET",
                status_code=200,
                ip_address="203.0.113.5",
                timestamp=datetime.now(UTC).isoformat(),
            )
        )

        root_key = os.urandom(32)
        monkeypatch.setenv("RAI_ROOT_KEY", _root_key_env(root_key))
        monkeypatch.setenv("RAI_CRYPTO_ENVIRONMENT", "test")
        activated = await _module._activate_new_scheme_if_requested(engine)
        assert activated is True

        async with engine.raw.begin() as conn:
            await _module._refuse_if_unrecoverable_legacy_ciphertext(conn)
            count = await _module._rotate_table(conn, _module.audit_log, ["ip_address"])
        assert count == 1

        # Confirm it reads correctly through a *fresh* provider instance
        # with no legacy key available -- proof it's genuinely under
        # the new scheme now, not still legacy Fernet.
        clear_field_encryption_key()
        monkeypatch.delenv("RAI_FIELD_ENCRYPTION_KEY", raising=False)
        provider = LocalEnvelopeKeyProvider(
            root_key, environment="test", store=CryptoKeyRepository(engine)
        )
        key_id, dek = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, None)
        from responsibleai.db.encryption import configure_field_encryption_key

        configure_field_encryption_key(key_id, dek)
        rows = await repo.query(limit=10)
        assert rows[0]["ip_address"] == "203.0.113.5"
