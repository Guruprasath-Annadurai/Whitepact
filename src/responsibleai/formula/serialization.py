# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Deterministic canonical serialization and hashing."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any


def utc_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def canonical_json_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sha256(obj: Any) -> str:
    payload = canonical_json_dumps(obj).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
