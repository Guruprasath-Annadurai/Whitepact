# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Expected vs effective authority, compare, and structural drift."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.effective import EffectiveAuthoritySnapshot, load_effective_authority
from responsibleai.sovereign.manifest import WhitepactManifest
from responsibleai.sovereign.models import AuthorityComparison, AuthorityDriftReport, DriftFact
from responsibleai.sovereign.sources import SovereignCanonicalStore
from responsibleai.sovereign.tenant import assert_same_organization


class AuthorityDiffCategory(StrEnum):
    EXPECTED_AND_PRESENT = "EXPECTED_AND_PRESENT"
    EXPECTED_BUT_MISSING = "EXPECTED_BUT_MISSING"
    UNEXPECTED_EFFECTIVE = "UNEXPECTED_EFFECTIVE"
    UNKNOWN_EFFECTIVE_STATE = "UNKNOWN_EFFECTIVE_STATE"
    UNRESOLVED = "UNRESOLVED"


class ClassifiedAuthorityDiff(BaseModel):
    category: AuthorityDiffCategory
    capability_id: str
    authority_path: list[str] = Field(default_factory=list)
    note: str | None = None


class AuthorityCompareResult(BaseModel):
    organization_id: str
    expected_source: str = "whitepact.yaml manifest"
    effective_source: str = "delegation_repository + org_authority_ceiling"
    diffs: list[ClassifiedAuthorityDiff] = Field(default_factory=list)
    incomplete: bool = False
    incomplete_reason: str | None = None
    legacy: AuthorityComparison


async def compare_manifest_to_effective(
    store: SovereignCanonicalStore,
    ctx: SovereignContext,
    manifest: WhitepactManifest,
) -> AuthorityCompareResult:
    assert_same_organization(
        ctx.organization_id, manifest.organization_id, resource_kind="manifest"
    )
    effective = await load_effective_authority(
        store, ctx.organization_id, environment=ctx.environment
    )
    expected_ids = {c.capability_id for c in manifest.capabilities}
    effective_ids = set(effective.capability_ids)
    diffs: list[ClassifiedAuthorityDiff] = []
    for cap in sorted(expected_ids):
        if cap in effective_ids:
            diffs.append(
                ClassifiedAuthorityDiff(
                    category=AuthorityDiffCategory.EXPECTED_AND_PRESENT,
                    capability_id=cap,
                    authority_path=effective.provenance,
                )
            )
        else:
            diffs.append(
                ClassifiedAuthorityDiff(
                    category=AuthorityDiffCategory.EXPECTED_BUT_MISSING,
                    capability_id=cap,
                    note="Declared in manifest but not in effective delegation-derived set",
                )
            )
    for cap in sorted(effective_ids - expected_ids):
        diffs.append(
            ClassifiedAuthorityDiff(
                category=AuthorityDiffCategory.UNEXPECTED_EFFECTIVE,
                capability_id=cap,
                authority_path=effective.provenance,
                note="Present in effective authority but not declared in manifest",
            )
        )
    incomplete = bool(effective.unknown_fields)
    legacy = AuthorityComparison(
        organization_id=ctx.organization_id,
        expected_only=sorted(expected_ids - effective_ids),
        effective_only=sorted(effective_ids - expected_ids),
        shared=sorted(expected_ids & effective_ids),
        notes=[
            "Manifest declares expected authority only; it does not grant capabilities",
            f"Effective provenance: {', '.join(effective.provenance)}",
        ],
    )
    return AuthorityCompareResult(
        organization_id=ctx.organization_id,
        diffs=diffs,
        incomplete=incomplete,
        incomplete_reason=(
            "Effective snapshot has unknown fields: " + ", ".join(effective.unknown_fields)
            if incomplete
            else None
        ),
        legacy=legacy,
    )


async def detect_structural_drift(
    store: SovereignCanonicalStore,
    ctx: SovereignContext,
    manifest: WhitepactManifest,
    *,
    prior_effective: EffectiveAuthoritySnapshot | None = None,
) -> AuthorityDriftReport:
    compare = await compare_manifest_to_effective(store, ctx, manifest)
    effective = await load_effective_authority(
        store, ctx.organization_id, environment=ctx.environment
    )
    facts: list[DriftFact] = []
    for diff in compare.diffs:
        if diff.category == AuthorityDiffCategory.EXPECTED_BUT_MISSING:
            facts.append(
                DriftFact(
                    code="expected_capability_removed",
                    message=f"Expected capability {diff.capability_id} missing from effective authority",
                    expected_ref=diff.capability_id,
                )
            )
        elif diff.category == AuthorityDiffCategory.UNEXPECTED_EFFECTIVE:
            facts.append(
                DriftFact(
                    code="unexpected_capability_added",
                    message=f"Effective capability {diff.capability_id} not declared in manifest",
                    effective_ref=diff.capability_id,
                )
            )

    if prior_effective is not None:
        assert_same_organization(
            ctx.organization_id, prior_effective.organization_id, resource_kind="snapshot"
        )
        before = set(prior_effective.capability_ids)
        after = set(effective.capability_ids)
        for cap in sorted(after - before):
            facts.append(
                DriftFact(
                    code="transitive_path_appeared",
                    message=f"Capability {cap} appeared since prior snapshot",
                    effective_ref=cap,
                )
            )
        for cap in sorted(before - after):
            facts.append(
                DriftFact(
                    code="transitive_path_disappeared",
                    message=f"Capability {cap} absent vs prior snapshot",
                    expected_ref=cap,
                )
            )
        if prior_effective.policy_version != effective.policy_version:
            facts.append(
                DriftFact(
                    code="policy_binding_changed",
                    message=(
                        f"Policy version {prior_effective.policy_version} -> "
                        f"{effective.policy_version}"
                    ),
                )
            )
        if prior_effective.governance_epoch != effective.governance_epoch:
            facts.append(
                DriftFact(
                    code="revocation_changed",
                    message=(
                        f"Governance epoch {prior_effective.governance_epoch} -> "
                        f"{effective.governance_epoch}"
                    ),
                )
            )

    if manifest.environment != ctx.environment:
        facts.append(
            DriftFact(
                code="environment_changed",
                message=f"Context environment {ctx.environment} differs from manifest {manifest.environment}",
            )
        )

    return AuthorityDriftReport(organization_id=ctx.organization_id, facts=facts)


async def compare_effective_snapshots(
    ctx: SovereignContext,
    left: EffectiveAuthoritySnapshot,
    right: EffectiveAuthoritySnapshot,
) -> AuthorityCompareResult:
    assert_same_organization(ctx.organization_id, left.organization_id, resource_kind="snapshot")
    assert_same_organization(ctx.organization_id, right.organization_id, resource_kind="snapshot")
    expected_ids = set(left.capability_ids)
    effective_ids = set(right.capability_ids)
    diffs: list[ClassifiedAuthorityDiff] = []
    for cap in sorted(expected_ids & effective_ids):
        diffs.append(
            ClassifiedAuthorityDiff(
                category=AuthorityDiffCategory.EXPECTED_AND_PRESENT,
                capability_id=cap,
            )
        )
    for cap in sorted(expected_ids - effective_ids):
        diffs.append(
            ClassifiedAuthorityDiff(
                category=AuthorityDiffCategory.EXPECTED_BUT_MISSING,
                capability_id=cap,
                note="Present in left snapshot only",
            )
        )
    for cap in sorted(effective_ids - expected_ids):
        diffs.append(
            ClassifiedAuthorityDiff(
                category=AuthorityDiffCategory.UNEXPECTED_EFFECTIVE,
                capability_id=cap,
                note="Present in right snapshot only",
            )
        )
    legacy = AuthorityComparison(
        organization_id=ctx.organization_id,
        expected_only=sorted(expected_ids - effective_ids),
        effective_only=sorted(effective_ids - expected_ids),
        shared=sorted(expected_ids & effective_ids),
        notes=["Snapshot A vs snapshot B comparison"],
    )
    return AuthorityCompareResult(
        organization_id=ctx.organization_id,
        effective_source="effective_authority_snapshot",
        expected_source="effective_authority_snapshot",
        diffs=diffs,
        legacy=legacy,
    )
