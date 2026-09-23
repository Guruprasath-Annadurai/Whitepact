# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
import os
from typing import Any

from responsibleai.global_directory.person.hints import PersonQueryHints

logger = logging.getLogger(__name__)


class GitHubPublicProvider:
    """Optional live GitHub user lookup. Degrades to no results when unconfigured."""

    name = "github_public"

    def discover(self, query: str, hints: PersonQueryHints) -> list[dict[str, Any]]:
        token = os.environ.get("WHITEPACT_GLOBAL_DIRECTORY_GITHUB_TOKEN", "").strip()
        if not token:
            return []
        if not hints.github_handle and not hints.name_tokens:
            return []
        # Live HTTP search is egress-gated; full implementation deferred to configured environments.
        logger.debug("github_public_discovery_skipped token_configured=%s", bool(token))
        return []
