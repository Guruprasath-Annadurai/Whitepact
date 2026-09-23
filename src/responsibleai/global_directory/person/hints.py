# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import re
from dataclasses import dataclass, field

from responsibleai.global_directory.identifiers import extract_identifiers, normalize_free_text

# Hints are disambiguation aids only — never treated as verified facts until corroborated.
_ORG_HINT = re.compile(
    r"\b(?:at|from|with|for|@)\s+(?P<org>[A-Za-z0-9][A-Za-z0-9 .&'-]{1,80})",
    re.IGNORECASE,
)
_WORKING_AT = re.compile(
    r"\bworking\s+at\s+(?P<org>[A-Za-z0-9][A-Za-z0-9 .&'-]{1,80})",
    re.IGNORECASE,
)
_PROFESSION = re.compile(
    r"\b(?:as\s+a?|role\s+of)\s+(?P<prof>[a-z][a-z\s]{2,40})",
    re.IGNORECASE,
)
_GITHUB_HANDLE = re.compile(r"\bgithub\.com/(?P<user>[A-Za-z0-9-]+)\b", re.IGNORECASE)
_PROFILE_URL = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_REPO_HINT = re.compile(r"\b(?:repo(?:sitory)?|project)\s+(?P<repo>[\w./-]+)", re.IGNORECASE)


@dataclass
class PersonQueryHints:
    raw_query: str
    normalized_query: str
    name_tokens: list[str] = field(default_factory=list)
    organization_hint: str | None = None
    profession_hint: str | None = None
    project_hint: str | None = None
    repository_hint: str | None = None
    github_handle: str | None = None
    profile_urls: list[str] = field(default_factory=list)
    domain_hint: str | None = None
    location_hint: str | None = None

    @property
    def display_name(self) -> str:
        return " ".join(self.name_tokens) if self.name_tokens else self.normalized_query


def extract_person_hints(query: str) -> PersonQueryHints:
    normalized = normalize_free_text(query)
    identifiers = extract_identifiers(query)
    github_handle = None
    domain_hint = None
    for ident in identifiers:
        if ident.identifier_type == "github_user":
            github_handle = ident.normalized_value.split("/")[-1]
        if ident.identifier_type == "domain":
            domain_hint = ident.normalized_value

    org = None
    for pattern in (_WORKING_AT, _ORG_HINT):
        m = pattern.search(query)
        if m:
            org = m.group("org").strip().rstrip(".,;")
            break

    prof = None
    pm = _PROFESSION.search(query)
    if pm:
        prof = pm.group("prof").strip()

    repo = None
    rm = _REPO_HINT.search(query)
    if rm:
        repo = rm.group("repo").strip()

    gh = _GITHUB_HANDLE.search(query)
    if gh and not github_handle:
        github_handle = gh.group("user")

    profile_urls = _PROFILE_URL.findall(query)

    # Name: strip hint clauses heuristically
    name_source = query
    for strip_pat in (
        r"\b(?:tell me about|who is|about)\s+",
        r"\bworking\s+at\s+[^,?]+",
        r"\b(?:at|from|with|for|@)\s+[^,?]+",
        r"\b(?:as\s+a?|role\s+of)\s+[^,?]+",
    ):
        name_source = re.sub(strip_pat, " ", name_source, flags=re.IGNORECASE)
    name_source = re.sub(_PROFILE_URL, " ", name_source)
    name_source = re.sub(_GITHUB_HANDLE, " ", name_source)
    name_tokens = [t for t in normalize_free_text(name_source).split() if t and len(t) > 1]

    return PersonQueryHints(
        raw_query=query,
        normalized_query=normalized,
        name_tokens=name_tokens,
        organization_hint=org,
        profession_hint=prof,
        project_hint=None,
        repository_hint=repo,
        github_handle=github_handle,
        profile_urls=profile_urls,
        domain_hint=domain_hint,
    )


def _looks_like_person_name_token(token: str) -> bool:
    if len(token) < 2 or not token.isalpha():
        return False
    # Internal capitals usually indicate organization/brand names (e.g. WhitePact).
    return not any(c.isupper() for c in token[1:])


def is_person_primary_query(query: str) -> bool:
    """True when the query should enter the person resolution pipeline."""
    identifiers = extract_identifiers(query)
    for ident in identifiers:
        if ident.implied_entity_type and ident.implied_entity_type.value not in {"PERSON"}:
            return False
        if ident.identifier_type == "github_user":
            return True
    lowered = query.casefold()
    if any(k in lowered for k in ("who is", "tell me about", "working at", "engineer", "founder", "researcher")):
        return True
    hints = extract_person_hints(query)
    if hints.organization_hint and hints.name_tokens:
        return True
    # Short free-text without domain/repo path → treat as person name query
    if "github.com/" in lowered and "/" in lowered.split("github.com/", 1)[-1]:
        return False
    if "." in query and " " not in query.strip():
        return False
    if 2 <= len(hints.name_tokens) <= 4:
        return True
    raw_tokens = [t for t in query.strip().split() if t]
    if len(raw_tokens) == 1 and any(c.isupper() for c in raw_tokens[0][1:]):
        return False
    if len(hints.name_tokens) == 1 and _looks_like_person_name_token(hints.name_tokens[0]):
        return True
    return False
