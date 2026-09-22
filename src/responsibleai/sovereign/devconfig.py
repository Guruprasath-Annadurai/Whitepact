# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Local developer configuration — never stores secrets."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

CONFIG_DIR = Path.home() / ".whitepact"
CONTEXT_FILE = CONFIG_DIR / "context.json"
MANIFEST_HINT = Path("whitepact.yaml")


@dataclass
class SovereignConnection:
    base_url: str = "http://127.0.0.1:8000"
    organization_id: str | None = None
    environment: str = "development"


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_connection() -> SovereignConnection:
    if not CONTEXT_FILE.is_file():
        return SovereignConnection()
    data = json.loads(CONTEXT_FILE.read_text(encoding="utf-8"))
    return SovereignConnection(
        base_url=data.get("base_url", "http://127.0.0.1:8000"),
        organization_id=data.get("organization_id"),
        environment=data.get("environment", "development"),
    )


def save_connection(conn: SovereignConnection) -> None:
    ensure_config_dir()
    CONTEXT_FILE.write_text(
        json.dumps(
            {
                "base_url": conn.base_url,
                "organization_id": conn.organization_id,
                "environment": conn.environment,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def init_scaffolding(target: Path) -> Path:
    manifest = target / "whitepact.yaml"
    if manifest.exists():
        return manifest
    manifest.write_text(
        "schema_version: '1.0'\n"
        "organization_id: dev-org\n"
        "environment: development\n"
        "capabilities: []\n"
        "actors: []\n"
        "delegations: []\n"
        "policies: []\n",
        encoding="utf-8",
    )
    return manifest
