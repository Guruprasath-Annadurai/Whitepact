# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Database Schema Introspection and Data Inventory for WhitePact Phase 5."""

from __future__ import annotations

from typing import Any

from responsibleai.data_governance.classification import (
    TABLE_CLASSIFICATIONS,
    DataClassification,
    TableClassification,
    classify_table,
)
from responsibleai.db.engine import DatabaseEngine, metadata


class DataInventoryManager:
    """Audits persistent tables, foreign keys, and classification coverage."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    def get_registered_tables(self) -> list[str]:
        """Return all tables registered in SQLAlchemy metadata."""
        return sorted(metadata.tables.keys())

    def get_inventory_summary(self) -> dict[str, Any]:
        """Return inventory summary breakdown by data classification."""
        tables = self.get_registered_tables()
        classification_counts: dict[str, int] = {c.value: 0 for c in DataClassification}
        classified_tables: list[TableClassification] = []
        unclassified_tables: list[str] = []

        for t in tables:
            cl = classify_table(t)
            classified_tables.append(cl)
            classification_counts[cl.classification.value] += 1
            if t not in TABLE_CLASSIFICATIONS:
                unclassified_tables.append(t)

        return {
            "total_tables": len(tables),
            "unclassified_count": len(unclassified_tables),
            "unclassified_tables": unclassified_tables,
            "classification_breakdown": classification_counts,
            "tables": [
                {
                    "table_name": ct.table_name,
                    "classification": ct.classification.value,
                    "sensitivity": ct.sensitivity.value,
                    "exportable": ct.exportable,
                    "erasable": ct.erasable,
                }
                for ct in classified_tables
            ],
        }
