# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Name-only secret and configuration checks. Values are never returned."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

# Names only. Values stay in the operator environment.
TERRAFORM_SECRET_NAMES = ("HCLOUD_TOKEN",)
BACKUP_SECRET_NAMES = (
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET",
    "R2_ENDPOINT",
    "WHITEPACT_BACKUP_ENCRYPTION_KEY",
)
STAGING_APP_SECRET_NAMES = (
    "POSTGRES_PASSWORD",
    "REDIS_PASSWORD",
)
EDGE_SECRET_NAMES = ("CLOUDFLARE_API_TOKEN",)

_PLACEHOLDERS = frozenset(
    {
        "replace_before_apply",
        "changeme",
        "change_me",
        "password",
        "secret",
        "todo",
        "xxx",
        "your.public.ip.address/32",
        "replace_with_hetzner_ssh_key_id",
    }
)


@dataclass(frozen=True)
class SecretCheck:
    name: str
    status: str


def _status(value: str | None) -> str:
    if value is None or not value.strip():
        return "missing"
    token = value.strip().casefold()
    if token in _PLACEHOLDERS or token.startswith("replace"):
        return "placeholder"
    return "present"


def review_secrets(env: Mapping[str, str], names: tuple[str, ...]) -> tuple[SecretCheck, ...]:
    return tuple(SecretCheck(name, _status(env.get(name))) for name in names)


def review_staging_secrets(env: Mapping[str, str]) -> tuple[SecretCheck, ...]:
    names = TERRAFORM_SECRET_NAMES + BACKUP_SECRET_NAMES + STAGING_APP_SECRET_NAMES + EDGE_SECRET_NAMES
    return review_secrets(env, names)


def blocked_names(checks: tuple[SecretCheck, ...]) -> tuple[str, ...]:
    return tuple(item.name for item in checks if item.status != "present")
