"""Tests for Enterprise Neural Phase 4 Step 2 —
`db/neural_vault_repository.py`'s `NeuralConsentRepository` and
`NeuralVaultRepository`. See `docs/enterprise-neural/04_PHASE4_DESIGN.md`
Sec 6-7.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from responsibleai.db.engine import DatabaseEngine, create_engine
from responsibleai.db.neural_vault_repository import (
    NeuralConsentRepository,
    NeuralVaultEntryNotFoundError,
    NeuralVaultRepository,
)
from responsibleai.governance.neural import (
    ConsentCategory,
    ConsentRecord,
    ConsentStatus,
    NeuralDataClass,
    NeuralVaultEntry,
)


async def _engine() -> DatabaseEngine:
    engine = create_engine(":memory:")
    await engine.init()
    return engine


def _consent(
    subject_id: str = "u1",
    category: ConsentCategory = ConsentCategory.BCI_CONNECTION,
    status: ConsentStatus = ConsentStatus.GRANTED,
    version: int = 1,
) -> ConsentRecord:
    return ConsentRecord(
        consent_id=f"{subject_id}:{category.value}:v{version}",
        subject_id=subject_id,
        organization_id=None,
        category=category,
        status=status,
        version=version,
        granted_at=datetime.now(UTC),
        revoked_at=datetime.now(UTC) if status is ConsentStatus.REVOKED else None,
    )


def _vault_entry(
    entry_id: str = "e1",
    subject_id: str = "u1",
    session_id: str = "s1",
    data_class: NeuralDataClass = NeuralDataClass.N3_NEURAL_INFERENCE,
) -> NeuralVaultEntry:
    return NeuralVaultEntry(
        entry_id=entry_id,
        subject_id=subject_id,
        session_id=session_id,
        data_class=data_class,
        captured_at=datetime.now(UTC),
    )


class TestNeuralConsentRepository:
    async def test_grant_then_get_active_round_trips(self) -> None:
        repo = NeuralConsentRepository(await _engine())
        record = _consent()
        await repo.grant(record)
        active = await repo.get_active("u1", ConsentCategory.BCI_CONNECTION)
        assert active == record

    async def test_get_active_on_empty_store_returns_none(self) -> None:
        repo = NeuralConsentRepository(await _engine())
        assert await repo.get_active("u1", ConsentCategory.BCI_CONNECTION) is None

    async def test_revoke_with_no_prior_grant_starts_at_version_one(self) -> None:
        repo = NeuralConsentRepository(await _engine())
        revoked = await repo.revoke("u1", None, ConsentCategory.BCI_CONNECTION)
        assert revoked.version == 1
        assert not revoked.is_active

    async def test_revoke_after_grant_creates_next_version(self) -> None:
        repo = NeuralConsentRepository(await _engine())
        await repo.grant(_consent(version=1))
        revoked = await repo.revoke("u1", None, ConsentCategory.BCI_CONNECTION)
        assert revoked.version == 2
        active = await repo.get_active("u1", ConsentCategory.BCI_CONNECTION)
        assert active is not None
        assert active.version == 2
        assert not active.is_active

    async def test_list_for_subject_preserves_full_audit_trail(self) -> None:
        repo = NeuralConsentRepository(await _engine())
        await repo.grant(_consent(version=1))
        await repo.revoke("u1", None, ConsentCategory.BCI_CONNECTION)
        records = await repo.list_for_subject("u1")
        assert len(records) == 2
        assert {r.version for r in records} == {1, 2}

    async def test_list_for_subject_filters_by_category(self) -> None:
        repo = NeuralConsentRepository(await _engine())
        await repo.grant(_consent(category=ConsentCategory.BCI_CONNECTION))
        await repo.grant(_consent(category=ConsentCategory.RESEARCH_CONTRIBUTION))
        records = await repo.list_for_subject("u1", category=ConsentCategory.BCI_CONNECTION)
        assert len(records) == 1
        assert records[0].category is ConsentCategory.BCI_CONNECTION

    async def test_different_subjects_are_isolated(self) -> None:
        repo = NeuralConsentRepository(await _engine())
        await repo.grant(_consent(subject_id="u1"))
        assert await repo.get_active("u2", ConsentCategory.BCI_CONNECTION) is None

    async def test_get_active_returns_the_highest_version(self) -> None:
        repo = NeuralConsentRepository(await _engine())
        await repo.grant(_consent(version=1, status=ConsentStatus.GRANTED))
        await repo.grant(_consent(version=2, status=ConsentStatus.REVOKED))
        await repo.grant(_consent(version=3, status=ConsentStatus.GRANTED))
        active = await repo.get_active("u1", ConsentCategory.BCI_CONNECTION)
        assert active is not None
        assert active.version == 3


class TestNeuralVaultRepository:
    async def test_create_then_get_round_trips(self) -> None:
        repo = NeuralVaultRepository(await _engine())
        entry = _vault_entry()
        await repo.create_entry(entry)
        fetched = await repo.get("e1")
        assert fetched == entry

    async def test_get_on_missing_entry_returns_none(self) -> None:
        repo = NeuralVaultRepository(await _engine())
        assert await repo.get("missing") is None

    async def test_list_for_subject_returns_only_that_subjects_entries(self) -> None:
        repo = NeuralVaultRepository(await _engine())
        await repo.create_entry(_vault_entry(entry_id="e1", subject_id="u1"))
        await repo.create_entry(_vault_entry(entry_id="e2", subject_id="u2"))
        listed = await repo.list_for_subject("u1")
        assert [e.entry_id for e in listed] == ["e1"]

    async def test_soft_delete_sets_deleted_at(self) -> None:
        repo = NeuralVaultRepository(await _engine())
        await repo.create_entry(_vault_entry())
        deleted = await repo.soft_delete("e1")
        assert deleted.is_deleted
        assert deleted.deleted_at is not None

    async def test_soft_delete_on_unknown_entry_raises(self) -> None:
        repo = NeuralVaultRepository(await _engine())
        with pytest.raises(NeuralVaultEntryNotFoundError):
            await repo.soft_delete("missing")

    async def test_list_for_subject_excludes_deleted_by_default(self) -> None:
        repo = NeuralVaultRepository(await _engine())
        await repo.create_entry(_vault_entry())
        await repo.soft_delete("e1")
        assert await repo.list_for_subject("u1") == []

    async def test_list_for_subject_includes_deleted_when_requested(self) -> None:
        repo = NeuralVaultRepository(await _engine())
        await repo.create_entry(_vault_entry())
        await repo.soft_delete("e1")
        listed = await repo.list_for_subject("u1", include_deleted=True)
        assert len(listed) == 1
        assert listed[0].is_deleted

    async def test_encrypted_sync_copy_defaults_to_none(self) -> None:
        repo = NeuralVaultRepository(await _engine())
        await repo.create_entry(_vault_entry())
        fetched = await repo.get("e1")
        assert fetched is not None
        assert fetched.encrypted_sync_copy is None

    async def test_different_data_classes_round_trip_correctly(self) -> None:
        repo = NeuralVaultRepository(await _engine())
        for i, data_class in enumerate(NeuralDataClass):
            await repo.create_entry(_vault_entry(entry_id=f"e{i}", data_class=data_class))
        listed = await repo.list_for_subject("u1")
        assert {e.data_class for e in listed} == set(NeuralDataClass)
