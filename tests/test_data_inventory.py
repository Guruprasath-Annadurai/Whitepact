# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for Phase 5 Data Inventory & Schema Classification Coverage."""

from __future__ import annotations

import pytest

from responsibleai.data_governance.classification import (
    TABLE_CLASSIFICATIONS,
    DataClassification,
    SensitivityTier,
)
from responsibleai.data_governance.inventory import DataInventoryManager
from responsibleai.db.engine import DatabaseEngine, create_engine


@pytest.fixture
async def sqlite_engine():
    engine = create_engine(":memory:")
    await engine.init()
    yield engine
    await engine.close()


def test_complete_table_classification_coverage(sqlite_engine: DatabaseEngine):
    mgr = DataInventoryManager(sqlite_engine)
    summary = mgr.get_inventory_summary()

    # Total tables in schema
    assert summary["total_tables"] >= 51

    # Invariant: ZERO unclassified tables allowed in Phase 5
    assert summary["unclassified_count"] == 0, f"Unclassified tables found: {summary['unclassified_tables']}"


def test_critical_secret_tables_cannot_be_exported():
    crypto_keys = TABLE_CLASSIFICATIONS.get("governance_crypto_keys")
    assert crypto_keys is not None
    assert crypto_keys.classification == DataClassification.CREDENTIAL_SECRET
    assert crypto_keys.sensitivity == SensitivityTier.CRITICAL
    assert crypto_keys.exportable is False


def test_canonical_evidence_tables_cannot_be_erased():
    for ev_tbl in ["governance_evidence", "governance_evidence_chain_heads", "governance_root_authority_records"]:
        entry = TABLE_CLASSIFICATIONS.get(ev_tbl)
        assert entry is not None
        assert entry.classification == DataClassification.CANONICAL_SECURITY_EVIDENCE
        assert entry.erasable is False
