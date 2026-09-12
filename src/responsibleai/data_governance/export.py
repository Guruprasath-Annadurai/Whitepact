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
    governance_approvals,
    governance_policies,
    incidents,
    token_usage,
    tool_trust_scores,
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
    }
)


@dataclass(frozen=True)
class ExportManifest:
    export_id: str
    org_id: str
    requested_by: str
    exported_at: str
    record_counts: dict[str, int]
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
        """Extract, sanitize, and bundle all exportable data for org_id."""
        export_id = str(uuid.uuid4())
        now = _now()
        data: dict[str, list[dict[str, Any]]] = {}
        record_counts: dict[str, int] = {}

        # Tables to extract for tenant export
        exportable_tables = [
            ("incidents", incidents, "org_id"),
            ("governance_policies", governance_policies, "org_id"),
            ("governance_approvals", governance_approvals, "org_id"),
            ("tool_trust_scores", tool_trust_scores, "org_id"),
            ("token_usage", token_usage, "org_id"),
        ]

        async with self._engine.raw.connect() as conn:
            for table_name, tbl, org_col in exportable_tables:
                # Confirm table is exportable and not CREDENTIAL_SECRET
                classification = TABLE_CLASSIFICATIONS.get(table_name)
                if classification and classification.classification == DataClassification.CREDENTIAL_SECRET:
                    continue
                if classification and not classification.exportable:
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

        # Compute deterministic integrity digest over extracted data
        serialized_data = json.dumps(data, sort_keys=True, separators=(",", ":"))
        integrity_digest = hashlib.sha256(serialized_data.encode("utf-8")).hexdigest()

        manifest = ExportManifest(
            export_id=export_id,
            org_id=org_id,
            requested_by=requested_by,
            exported_at=now,
            record_counts=record_counts,
            integrity_digest=integrity_digest,
        )

        return TenantExportBundle(manifest=manifest, data=data)
