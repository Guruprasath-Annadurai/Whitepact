# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Structured Tenant Data Export Service for WhitePact Phase 5.

Features:
- Deterministic manifest generation with SHA-256 integrity digest.
- Strict isolation: exports data scoped exclusively to caller's org_id.
- Zero-Secret Export: automatically strips passwords, crypto keys, and session secrets.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from responsibleai.data_governance.classification import (
    TABLE_CLASSIFICATIONS,
    DataClassification,
)
from responsibleai.db.engine import (
    DatabaseEngine,
    metadata,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


SECRET_COLUMNS = frozenset(
    {
        "password_hash",
        "secret_key",
        "private_key",
        "key_hash",
        "symmetric_key",
        "totp_secret",
        "session_secret",
        "token_hash",
        "nonce_hash",
        "wrapped_dek",
        "mfa_secret",
        "mfa_backup_codes",
        "client_secret",
        "raw_token",
    }
)


@dataclass(frozen=True)
class ExportManifest:
    export_id: str
    org_id: str
    requested_by: str
    exported_at: str
    schema_version: str
    record_counts: dict[str, int]
    included_tables: list[str]
    excluded_tables: dict[str, str]
    integrity_digest: str


@dataclass(frozen=True)
class TenantExportBundle:
    manifest: ExportManifest
    data: dict[str, list[dict[str, Any]]]

    def to_json(self) -> str:
        return json.dumps(
            {
                "manifest": asdict(self.manifest),
                "data": self.data,
            },
            indent=2,
            sort_keys=True,
        )


class DataExportService:
    """Generates cryptographically sealed, sanitized tenant export packages."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def export_tenant_data(self, org_id: str, requested_by: str) -> TenantExportBundle:
        """Extract, sanitize, and bundle all exportable data for org_id with transparent manifest."""
        export_id = str(uuid.uuid4())
        now = _now()
        data: dict[str, list[dict[str, Any]]] = {}
        record_counts: dict[str, int] = {}
        included_tables: list[str] = []
        excluded_tables: dict[str, str] = {}

        # Categorize all registered tables according to TABLE_CLASSIFICATIONS
        all_tables = sorted(metadata.tables.keys())
        for table_name in all_tables:
            classification = TABLE_CLASSIFICATIONS.get(table_name)
            if classification is None:
                excluded_tables[table_name] = "EXCLUDED_UNCLASSIFIED: fail-closed policy prohibits export"
            elif classification.classification == DataClassification.CREDENTIAL_SECRET:
                excluded_tables[table_name] = "EXCLUDED_CREDENTIAL_SECRET: zero-secret export security policy"
            elif classification.classification == DataClassification.SYSTEM_METADATA:
                excluded_tables[table_name] = "EXCLUDED_SYSTEM_METADATA: internal infrastructure metadata"
            elif not classification.exportable:
                excluded_tables[table_name] = "EXCLUDED_NON_EXPORTABLE: table policy prohibits export"
            else:
                included_tables.append(table_name)

        async with self._engine.raw.connect() as conn:
            for table_name in included_tables:
                tbl = metadata.tables[table_name]
                # Identify tenant foreign key column
                org_col = None
                for candidate in ["org_id", "tenant_id", "organization_id"]:
                    if hasattr(tbl.c, candidate):
                        org_col = candidate
                        break

                if org_col is None:
                    # Table is exportable in principle but shared/not tenant-partitioned
                    excluded_tables[table_name] = "EXCLUDED_SHARED_TABLE: no tenant-specific partition column"
                    continue

                col_attr = getattr(tbl.c, org_col)
                query = select(tbl).where(col_attr == org_id)
                rows = (await conn.execute(query)).fetchall()

                cleaned_rows: list[dict[str, Any]] = []
                for r in rows:
                    r_dict = dict(r._mapping)
                    # Filter out any secret columns
                    sanitized = {k: v for k, v in r_dict.items() if k not in SECRET_COLUMNS}
                    cleaned_rows.append(sanitized)

                data[table_name] = cleaned_rows
                record_counts[table_name] = len(cleaned_rows)

        # Remove tables that were excluded due to being shared from included_tables
        final_included = sorted([t for t in included_tables if t not in excluded_tables])

        # Compute deterministic integrity digest over extracted data
        serialized_data = json.dumps(data, sort_keys=True, separators=(",", ":"))
        integrity_digest = hashlib.sha256(serialized_data.encode("utf-8")).hexdigest()

        manifest = ExportManifest(
            export_id=export_id,
            org_id=org_id,
            requested_by=requested_by,
            exported_at=now,
            schema_version="0045",
            record_counts=record_counts,
            included_tables=final_included,
            excluded_tables=excluded_tables,
            integrity_digest=integrity_digest,
        )

        return TenantExportBundle(manifest=manifest, data=data)
