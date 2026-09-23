# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
from typing import Any, Protocol

from responsibleai.global_directory.person.hints import PersonQueryHints


class DiscoveryProvider(Protocol):
    name: str

    def discover(self, query: str, hints: PersonQueryHints) -> list[dict[str, Any]]:
        """Return raw catalog-shaped entity entries (public professional evidence only)."""


def build_discovery_providers() -> list[DiscoveryProvider]:
    from responsibleai.global_directory.discovery.providers.fixture_catalog import (
        FixtureCatalogProvider,
    )
    from responsibleai.global_directory.discovery.providers.github_public import (
        GitHubPublicProvider,
    )
    from responsibleai.global_directory.discovery.providers.web_search import (
        ConfigurableWebSearchProvider,
    )

    providers: list[DiscoveryProvider] = []
    if _fixture_enabled():
        providers.append(FixtureCatalogProvider())
    providers.append(GitHubPublicProvider())
    providers.append(ConfigurableWebSearchProvider())
    return providers


def _fixture_enabled() -> bool:
    return os.environ.get("WHITEPACT_GLOBAL_DIRECTORY_FIXTURE_DISCOVERY", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )
