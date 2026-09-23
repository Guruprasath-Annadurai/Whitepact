# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlparse

from responsibleai.global_directory.enums import EntityType


@dataclass(frozen=True)
class ParsedIdentifier:
    identifier_type: str
    normalized_value: str
    implied_entity_type: EntityType | None = None


_GITHUB_REPO = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/(?P<owner>[^/\s]+)/(?P<repo>[^/\s#?]+)",
    re.IGNORECASE,
)
_GITHUB_USER = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/(?P<owner>[^/\s#?]+)/?$",
    re.IGNORECASE,
)
_DOMAIN = re.compile(
    r"^(?:https?://)?(?P<host>(?:[a-z0-9-]+\.)+[a-z]{2,})(?:/|$)",
    re.IGNORECASE,
)


def normalize_free_text(value: str) -> str:
    collapsed = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    return collapsed.casefold()


def extract_identifiers(query: str) -> list[ParsedIdentifier]:
    raw = query.strip()
    identifiers: list[ParsedIdentifier] = []
    if not raw:
        return identifiers

    repo = _GITHUB_REPO.match(raw)
    if repo:
        owner, repo_name = repo.group("owner"), repo.group("repo")
        identifiers.append(
            ParsedIdentifier(
                "github_repository",
                f"github.com/{owner.lower()}/{repo_name.lower()}",
                EntityType.REPOSITORY,
            )
        )
        return identifiers

    user = _GITHUB_USER.match(raw)
    if user:
        owner = user.group("owner").lower()
        if owner not in {"orgs", "organizations", "settings", "marketplace"}:
            identifiers.append(
                ParsedIdentifier("github_user", f"github.com/{owner}", EntityType.PERSON)
            )
        return identifiers

    domain = _DOMAIN.match(raw)
    if domain:
        host = domain.group("host").lower().rstrip(".")
        identifiers.append(
            ParsedIdentifier("domain", host, EntityType.DOMAIN)
        )
        return identifiers

    if "." in raw and " " not in raw and not raw.startswith("http"):
        identifiers.append(
            ParsedIdentifier("domain", raw.lower().rstrip("."), EntityType.DOMAIN)
        )
    return identifiers
