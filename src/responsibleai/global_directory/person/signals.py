# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from responsibleai.global_directory.enums import FreshnessState, SourceQualityTier
from responsibleai.global_directory.identifiers import normalize_free_text
from responsibleai.global_directory.person.hints import PersonQueryHints


class IdentitySignalKind(StrEnum):
    CANONICAL_NAME_MATCH = "canonical_name_match"
    ALIAS_MATCH = "alias_match"
    EMPLOYER_MATCH = "employer_match"
    PROJECT_MATCH = "project_match"
    REPOSITORY_MATCH = "repository_match"
    DOMAIN_MATCH = "domain_match"
    PUBLIC_HANDLE_MATCH = "public_handle_match"
    OFFICIAL_PROFILE_MATCH = "official_profile_match"
    PUBLICATION_MATCH = "publication_match"
    FIRST_PARTY_BIOGRAPHY_MATCH = "first_party_biography_match"


class SignalPolarity(StrEnum):
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"


@dataclass
class IdentitySignal:
    kind: IdentitySignalKind
    weight: float
    source_id: str
    source_quality: SourceQualityTier
    freshness: FreshnessState
    polarity: SignalPolarity = SignalPolarity.SUPPORTING
    detail: str | None = None


@dataclass
class ScoredPersonCandidate:
    entity_key: str
    entity_id: str
    canonical_name: str
    professional_context: str
    signals: list[IdentitySignal] = field(default_factory=list)

    @property
    def score(self) -> float:
        if not self.signals:
            return 0.0
        total = 0.0
        for sig in self.signals:
            mult = 1.0 if sig.polarity == SignalPolarity.SUPPORTING else -0.5
            quality = {
                SourceQualityTier.AUTHORITATIVE_PRIMARY: 1.0,
                SourceQualityTier.AUTHORITATIVE_REGISTRY: 0.95,
                SourceQualityTier.FIRST_PARTY_PUBLICATION: 0.85,
                SourceQualityTier.HIGH_QUALITY_SECONDARY: 0.6,
                SourceQualityTier.COMMUNITY_SOURCE: 0.35,
                SourceQualityTier.UNKNOWN_SOURCE: 0.15,
            }.get(sig.source_quality, 0.2)
            total += sig.weight * quality * mult
        return max(0.0, min(1.0, total))


def _quality_from_entry(entry: dict) -> SourceQualityTier:
    sources = entry.get("sources") or []
    if not sources:
        return SourceQualityTier.UNKNOWN_SOURCE
    tier = sources[0].get("quality_tier", "UNKNOWN_SOURCE")
    try:
        return SourceQualityTier(tier)
    except ValueError:
        return SourceQualityTier.UNKNOWN_SOURCE


def build_signals_for_catalog_entry(entry: dict, hints: PersonQueryHints) -> list[IdentitySignal]:
    signals: list[IdentitySignal] = []
    source_id = "catalog"
    quality = _quality_from_entry(entry)
    canonical = normalize_free_text(entry.get("canonical_name", ""))
    name_norm = normalize_free_text(" ".join(hints.name_tokens)) if hints.name_tokens else hints.normalized_query

    if canonical == name_norm:
        signals.append(
            IdentitySignal(
                IdentitySignalKind.CANONICAL_NAME_MATCH,
                0.35,
                source_id,
                quality,
                FreshnessState.FRESH,
                detail="Exact canonical name match",
            )
        )
    elif canonical in name_norm or name_norm in canonical:
        signals.append(
            IdentitySignal(
                IdentitySignalKind.ALIAS_MATCH,
                0.25,
                source_id,
                quality,
                FreshnessState.FRESH,
            )
        )
    else:
        for alias in entry.get("aliases", []):
            if normalize_free_text(alias) == name_norm:
                signals.append(
                    IdentitySignal(
                        IdentitySignalKind.ALIAS_MATCH,
                        0.28,
                        source_id,
                        quality,
                        FreshnessState.FRESH,
                    )
                )
                break

    if hints.organization_hint:
        org_norm = normalize_free_text(hints.organization_hint)
        for claim in entry.get("claims", []):
            val = normalize_free_text(str(claim.get("normalized_value") or claim.get("object_name") or ""))
            if org_norm in val or val in org_norm:
                signals.append(
                    IdentitySignal(
                        IdentitySignalKind.EMPLOYER_MATCH,
                        0.45,
                        source_id,
                        quality,
                        FreshnessState.FRESH,
                        detail=f"Organization hint aligns with claim {claim.get('predicate')}",
                    )
                )

    if hints.github_handle:
        for ident in entry.get("identifiers", []):
            if ident.get("type") == "github_user" and hints.github_handle.casefold() in str(
                ident.get("value", "")
            ).casefold():
                signals.append(
                    IdentitySignal(
                        IdentitySignalKind.PUBLIC_HANDLE_MATCH,
                        0.5,
                        source_id,
                        SourceQualityTier.AUTHORITATIVE_REGISTRY,
                        FreshnessState.FRESH,
                    )
                )

    if hints.profession_hint and entry.get("description"):
        if hints.profession_hint.casefold() in entry["description"].casefold():
            signals.append(
                IdentitySignal(
                    IdentitySignalKind.FIRST_PARTY_BIOGRAPHY_MATCH,
                    0.2,
                    source_id,
                    quality,
                    FreshnessState.FRESH,
                )
            )

    # Claim-backed association/title signals require corroborating query hints to avoid
    # ranking one same-name candidate above peers from catalog metadata alone.
    if hints.organization_hint or hints.profession_hint or len(hints.name_tokens) >= 2:
        for claim in entry.get("claims", []):
            if claim.get("predicate") in {"ASSOCIATED_WITH", "TITLE"} and claim.get("normalized_value"):
                signals.append(
                    IdentitySignal(
                        IdentitySignalKind.EMPLOYER_MATCH
                        if claim["predicate"] == "ASSOCIATED_WITH"
                        else IdentitySignalKind.FIRST_PARTY_BIOGRAPHY_MATCH,
                        0.4,
                        source_id,
                        quality,
                        FreshnessState.FRESH,
                        detail=str(claim.get("normalized_value")),
                    )
                )

    # A single name match alone is never sufficient for identity proof.
    name_kinds = {IdentitySignalKind.CANONICAL_NAME_MATCH, IdentitySignalKind.ALIAS_MATCH}
    if signals and all(s.kind in name_kinds for s in signals) and len(signals) == 1:
        signals[0].weight = min(signals[0].weight, 0.2)

    return signals
