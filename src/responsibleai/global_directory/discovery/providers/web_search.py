# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
import os
from typing import Any

from responsibleai.global_directory.person.hints import PersonQueryHints

logger = logging.getLogger(__name__)


class ConfigurableWebSearchProvider:
    """Configurable general web search provider. No-op without API configuration."""

    name = "web_search"

    def discover(self, query: str, hints: PersonQueryHints) -> list[dict[str, Any]]:
        if not os.environ.get("WHITEPACT_GLOBAL_DIRECTORY_SEARCH_API_KEY", "").strip():
            return []
        logger.debug("web_search_discovery_skipped unconfigured")
        return []
