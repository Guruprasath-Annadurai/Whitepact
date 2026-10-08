# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Single hosted HSTS and robots policy.

The application middleware is the only HSTS authority. Cloudflare and the
origin proxy must not emit a second max-age. Preload is omitted unless the
operator sets both the preload flag and an explicit authorization flag.
"""

from __future__ import annotations

from typing import Literal

from responsibleai.dashboard.config import is_production_environment

HstsStage = Literal["disabled", "initial", "stage1", "stage2"]

_MAX_AGE: dict[str, int] = {
    "initial": 0,
    "stage1": 300,
    "stage2": 86400,
}


def resolved_hsts_stage(environment: str, stage: str | None) -> str:
    if stage:
        return stage
    if is_production_environment(environment):
        return "stage1"
    return "disabled"


def hsts_header_value(
    *,
    environment: str,
    stage: str | None,
    include_subdomains: bool | None,
    preload: bool,
    preload_authorized: bool,
) -> str | None:
    name = resolved_hsts_stage(environment, stage)
    if name == "disabled":
        return None
    if name not in _MAX_AGE:
        return None
    parts = [f"max-age={_MAX_AGE[name]}"]
    include = include_subdomains if include_subdomains is not None else name == "stage2"
    if include:
        parts.append("includeSubDomains")
    if preload and preload_authorized:
        parts.append("preload")
    return "; ".join(parts)


def preload_suppressed(*, preload: bool, preload_authorized: bool) -> bool:
    return bool(preload) and not preload_authorized


def robots_tag(*, environment: str, robots_noindex: bool | None) -> str | None:
    if robots_noindex is True:
        return "noindex, nofollow"
    if robots_noindex is False:
        return None
    if environment.strip().lower() == "staging":
        return "noindex, nofollow"
    return None
