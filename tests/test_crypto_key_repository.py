"""Tests for Enterprise Neural Phase 2 Step 2 —
`db/crypto_key_repository.py`'s `CryptoKeyRepository`, the DB-backed
`WrappedKeyStore` that replaces `InMemoryWrappedKeyStore`
(`governance/crypto/local_envelope.py`) for real deployments. Covers
the repository's own CRUD/query contract directly, plus end-to-end
behavior through `LocalEnvelopeKeyProvider` wired onto it (persistence
across separate repository instances against the same DB, simulating
a process restart) and the concurrency-safety property the DB-backed
store adds over the in-memory one: a `key_id` collision raises
`KeyVersionConflictError` instead of silently overwriting.
"""

from __future__ import annotations

import os

import pytest

from responsibleai.db.crypto_key_repository import CryptoKeyRepository
from responsibleai.db.engine import DatabaseEngine, create_engine
from responsibleai.governance.crypto import (
    KeyId,
    KeyNotFoundError,
    KeyPurpose,
    KeyRevokedError,
    KeyStatus,
    KeyVersionConflictError,
    LocalEnvelopeKeyProvider,
    WrappedKeyRecord,
)


async def _engine() -> DatabaseEngine:
    engine = create_engine(":memory:")
    await engine.init()
    return engine


def _key_id(
    purpose: KeyPurpose = KeyPurpose.FIELD_ENCRYPTION,
    tenant_id: str | None = "org1",
    version: int = 1,
    environment: str = "test",
) -> KeyId:
    return KeyId(purpose=purpose, tenant_id=tenant_id, version=version, environment=environment)


class TestCryptoKeyRepositoryCrud:
    async def test_get_on_empty_store_returns_none(self) -> None:
        repo = CryptoKeyRepository(await _engine())
        assert await repo.get(_key_id()) is None

    async def test_put_then_get_round_trips(self) -> None:
        repo = CryptoKeyRepository(await _engine())
        key_id = _key_id()
        record = WrappedKeyRecord(
            key_id=key_id, wrapped_dek=os.urandom(44), status=KeyStatus.ACTIVE
        )
        await repo.put(record)
        fetched = await repo.get(key_id)
        assert fetched == record

    async def test_put_duplicate_key_id_raises_version_conflict(self) -> None:
        repo = CryptoKeyRepository(await _engine())
        key_id = _key_id()
        await repo.put(
            WrappedKeyRecord(key_id=key_id, wrapped_dek=b"a" * 44, status=KeyStatus.ACTIVE)
        )
        with pytest.raises(KeyVersionConflictError):
            await repo.put(
                WrappedKeyRecord(key_id=key_id, wrapped_dek=b"b" * 44, status=KeyStatus.ACTIVE)
            )

    async def test_get_current_returns_none_when_nothing_active(self) -> None:
        repo = CryptoKeyRepository(await _engine())
        key_id = _key_id(version=1)
        await repo.put(
            WrappedKeyRecord(key_id=key_id, wrapped_dek=b"a" * 44, status=KeyStatus.RETIRED)
        )
        current = await repo.get_current(KeyPurpose.FIELD_ENCRYPTION, "org1", "test")
        assert current is None

    async def test_get_current_returns_highest_active_version(self) -> None:
        repo = CryptoKeyRepository(await _engine())
        await repo.put(
            WrappedKeyRecord(
                key_id=_key_id(version=1), wrapped_dek=b"a" * 44, status=KeyStatus.RETIRED
            )
        )
        await repo.put(
            WrappedKeyRecord(
                key_id=_key_id(version=2), wrapped_dek=b"b" * 44, status=KeyStatus.ACTIVE
            )
        )
        current = await repo.get_current(KeyPurpose.FIELD_ENCRYPTION, "org1", "test")
        assert current is not None
        assert current.key_id.version == 2

    async def test_get_max_version_ignores_status(self) -> None:
        """The whole point of get_max_version -- unlike get_current, it
        must see retired/revoked records too, or the version-numbering
        bug Step 1 fixed would resurface at the DB layer."""
        repo = CryptoKeyRepository(await _engine())
        await repo.put(
            WrappedKeyRecord(
                key_id=_key_id(version=1), wrapped_dek=b"a" * 44, status=KeyStatus.REVOKED
            )
        )
        assert await repo.get_max_version(KeyPurpose.FIELD_ENCRYPTION, "org1", "test") == 1

    async def test_get_max_version_on_empty_store_is_zero(self) -> None:
        repo = CryptoKeyRepository(await _engine())
        assert await repo.get_max_version(KeyPurpose.FIELD_ENCRYPTION, "org1", "test") == 0

    async def test_set_status_updates_and_persists(self) -> None:
        repo = CryptoKeyRepository(await _engine())
        key_id = _key_id()
        await repo.put(
            WrappedKeyRecord(key_id=key_id, wrapped_dek=b"a" * 44, status=KeyStatus.ACTIVE)
        )
        await repo.set_status(key_id, KeyStatus.REVOKED)
        fetched = await repo.get(key_id)
        assert fetched is not None
        assert fetched.status == KeyStatus.REVOKED

    async def test_set_status_on_unknown_key_raises_not_found(self) -> None:
        repo = CryptoKeyRepository(await _engine())
        with pytest.raises(KeyNotFoundError):
            await repo.set_status(_key_id(), KeyStatus.REVOKED)

    async def test_none_tenant_round_trips_through_the_reserved_empty_string_column(self) -> None:
        repo = CryptoKeyRepository(await _engine())
        key_id = _key_id(purpose=KeyPurpose.AUDIT_ANCHOR, tenant_id=None)
        await repo.put(
            WrappedKeyRecord(key_id=key_id, wrapped_dek=b"a" * 44, status=KeyStatus.ACTIVE)
        )
        fetched = await repo.get(key_id)
        assert fetched is not None
        assert fetched.key_id.tenant_id is None

    async def test_different_tenants_are_isolated_in_get_current(self) -> None:
        repo = CryptoKeyRepository(await _engine())
        await repo.put(
            WrappedKeyRecord(
                key_id=_key_id(tenant_id="org1", version=1),
                wrapped_dek=b"a" * 44,
                status=KeyStatus.ACTIVE,
            )
        )
        current_for_org2 = await repo.get_current(KeyPurpose.FIELD_ENCRYPTION, "org2", "test")
        assert current_for_org2 is None

    async def test_different_environments_are_isolated(self) -> None:
        repo = CryptoKeyRepository(await _engine())
        await repo.put(
            WrappedKeyRecord(
                key_id=_key_id(environment="dev", version=1),
                wrapped_dek=b"a" * 44,
                status=KeyStatus.ACTIVE,
            )
        )
        current_in_prod = await repo.get_current(KeyPurpose.FIELD_ENCRYPTION, "org1", "prod")
        assert current_in_prod is None


class TestLocalEnvelopeKeyProviderOverDbBackedStore:
    """End-to-end: LocalEnvelopeKeyProvider wired onto CryptoKeyRepository
    instead of InMemoryWrappedKeyStore -- the actual point of this
    repository existing."""

    async def test_encryption_key_persists_across_repository_instances(self) -> None:
        """Simulates a process restart: a fresh CryptoKeyRepository
        instance against the same underlying DB must resolve the same
        key a prior instance generated."""
        engine = await _engine()
        root_key = os.urandom(32)

        provider_a = LocalEnvelopeKeyProvider(
            root_key, environment="test", store=CryptoKeyRepository(engine)
        )
        key_id, dek = await provider_a.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")

        provider_b = LocalEnvelopeKeyProvider(
            root_key, environment="test", store=CryptoKeyRepository(engine)
        )
        resolved = await provider_b.get_decryption_key(key_id)
        assert resolved == dek

    async def test_rotation_and_revocation_work_over_db_backed_store(self) -> None:
        engine = await _engine()
        provider = LocalEnvelopeKeyProvider(
            os.urandom(32), environment="test", store=CryptoKeyRepository(engine)
        )
        old_key_id, old_dek = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        new_key_id = await provider.rotate(KeyPurpose.FIELD_ENCRYPTION, "org1")
        assert new_key_id.version == old_key_id.version + 1

        # Old key retired, not revoked -- still readable.
        assert await provider.get_decryption_key(old_key_id) == old_dek

        await provider.revoke(old_key_id)
        with pytest.raises(KeyRevokedError):
            await provider.get_decryption_key(old_key_id)

    async def test_retire_then_get_encryption_key_never_collides_over_db_backed_store(self) -> None:
        """Regression guard, DB-layer variant of Step 1's fixed bug: a
        collision here would raise KeyVersionConflictError (loudly)
        rather than silently overwrite, but it must not happen at all
        for the normal retire -> re-encrypt flow."""
        engine = await _engine()
        provider = LocalEnvelopeKeyProvider(
            os.urandom(32), environment="test", store=CryptoKeyRepository(engine)
        )
        key_id, _ = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        await provider.retire(key_id)
        new_key_id, _ = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, "org1")
        assert new_key_id.version == key_id.version + 1
