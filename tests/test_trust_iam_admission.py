# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial tests for the Trust Fabric -> IAM privileged admission gate.

Covers ``PrivilegedSurfaceGuard.authorize_privileged_operation(require_trust_admission=True)``:
the opt-in prerequisite check that consults the canonical, freshly-evaluated
``TrustProofEngine.prove_employment`` result before any role/step-up/four-eyes/JIT/
break-glass check runs. A PROVEN result is a prerequisite only -- it must not itself
grant privilege, so every scenario below still goes through the pre-existing checks.
"""

from __future__ import annotations

import pytest
from sqlalchemy import insert

from responsibleai.db.engine import DatabaseEngine, create_engine, organizations
from responsibleai.iam.enums import PrivilegedAction
from responsibleai.iam.errors import PrivilegedAccessDeniedError
from responsibleai.iam.guard import PrivilegedSurfaceGuard
from responsibleai.iam.models import PrivilegedCallerContext
from responsibleai.rbac.models import Role
from responsibleai.trust_fabric.authority_graph import AuthorityGraph
from responsibleai.trust_fabric.directory import PrincipalDirectory
from responsibleai.trust_fabric.enums import (
    IdentifierVerificationState,
    PrincipalType,
    RelationshipType,
    SourceTier,
)
from responsibleai.trust_fabric.provenance import TrustProvenanceEngine


@pytest.fixture
async def trust_iam_db(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path}/trust_iam.db"
    engine = create_engine(url)
    await engine.init()
    async with engine.raw.begin() as conn:
        for org_id, name, slug in (
            ("org_alpha", "Alpha Corp", "alpha-corp"),
            ("org_beta", "Beta Corp", "beta-corp"),
        ):
            await conn.execute(
                insert(organizations).values(
                    id=org_id,
                    name=name,
                    slug=slug,
                    monthly_budget_usd=10000.0,
                    created_at="2026-09-12T00:00:00Z",
                    plan="ENTERPRISE",
                )
            )
    try:
        yield engine
    finally:
        await engine.close()


async def _seed_employed_principal(
    engine: DatabaseEngine,
    *,
    org_id: str = "org_alpha",
    verification_state: IdentifierVerificationState = IdentifierVerificationState.VERIFIED,
    expires_at: str | None = None,
):
    """Create a principal with a verified EMPLOYED_BY relationship; return (principal_id, relationship_id)."""
    dir_svc = PrincipalDirectory(engine)
    auth_svc = AuthorityGraph(engine)
    prov_svc = TrustProvenanceEngine(engine)

    src = await prov_svc.register_source(
        name="HR Source", source_tier=SourceTier.TIER_C, provider_type="IDP", org_id=org_id
    )
    person = await dir_svc.create_principal(
        org_id=org_id, principal_type=PrincipalType.HUMAN, display_name="Admin Person"
    )
    company = await dir_svc.create_principal(
        org_id=org_id, principal_type=PrincipalType.ORGANIZATION, display_name="Company Entity"
    )
    rel = await auth_svc.create_relationship(
        subject_principal_id=person.id,
        target_principal_id=company.id,
        org_id=org_id,
        relationship_type=RelationshipType.EMPLOYED_BY,
        source_id=src.id,
        verification_state=verification_state,
        expires_at=expires_at,
    )
    return person.id, rel.id


def _caller(principal_id: str, org_id: str = "org_alpha", role: Role = Role.ADMIN) -> PrivilegedCallerContext:
    return PrivilegedCallerContext(principal_id=principal_id, org_id=org_id, role=role)


@pytest.mark.asyncio
async def test_default_behavior_unchanged_when_not_requested(trust_iam_db: DatabaseEngine):
    """Backward compatibility: existing callers who never pass require_trust_admission are unaffected."""
    guard = PrivilegedSurfaceGuard(trust_iam_db)
    caller = _caller("admin_no_trust_record")
    res = await guard.authorize_privileged_operation(
        caller=caller,
        target_org_id="org_alpha",
        action=PrivilegedAction.CREATE_API_KEY,
    )
    assert res.allowed is True


@pytest.mark.asyncio
async def test_proven_principal_with_valid_iam_allowed(trust_iam_db: DatabaseEngine):
    principal_id, _ = await _seed_employed_principal(trust_iam_db)
    guard = PrivilegedSurfaceGuard(trust_iam_db)
    res = await guard.authorize_privileged_operation(
        caller=_caller(principal_id),
        target_org_id="org_alpha",
        action=PrivilegedAction.CREATE_API_KEY,
        require_trust_admission=True,
    )
    assert res.allowed is True


@pytest.mark.asyncio
async def test_not_proven_principal_blocked(trust_iam_db: DatabaseEngine):
    # A real, registered principal with no employment relationship at all -> NOT_PROVEN
    # (distinct from UNKNOWN, which is for a principal the trust fabric has never heard of).
    dir_svc = PrincipalDirectory(trust_iam_db)
    person = await dir_svc.create_principal(
        org_id="org_alpha", principal_type=PrincipalType.HUMAN, display_name="No Relationship Person"
    )
    guard = PrivilegedSurfaceGuard(trust_iam_db)
    with pytest.raises(PrivilegedAccessDeniedError, match="NOT_PROVEN"):
        await guard.authorize_privileged_operation(
            caller=_caller(person.id),
            target_org_id="org_alpha",
            action=PrivilegedAction.CREATE_API_KEY,
            require_trust_admission=True,
        )


@pytest.mark.asyncio
async def test_unknown_principal_blocked(trust_iam_db: DatabaseEngine):
    guard = PrivilegedSurfaceGuard(trust_iam_db)
    # Principal not registered in the trust fabric at all -> UNKNOWN.
    with pytest.raises(PrivilegedAccessDeniedError, match="UNKNOWN"):
        await guard.authorize_privileged_operation(
            caller=_caller("ghost_principal_never_created"),
            target_org_id="org_alpha",
            action=PrivilegedAction.CREATE_API_KEY,
            require_trust_admission=True,
        )


@pytest.mark.asyncio
async def test_revoked_relationship_blocked(trust_iam_db: DatabaseEngine):
    principal_id, rel_id = await _seed_employed_principal(trust_iam_db)
    auth_svc = AuthorityGraph(trust_iam_db)
    await auth_svc.revoke_relationship(rel_id, org_id="org_alpha")

    guard = PrivilegedSurfaceGuard(trust_iam_db)
    with pytest.raises(PrivilegedAccessDeniedError, match="REVOKED"):
        await guard.authorize_privileged_operation(
            caller=_caller(principal_id),
            target_org_id="org_alpha",
            action=PrivilegedAction.CREATE_API_KEY,
            require_trust_admission=True,
        )


@pytest.mark.asyncio
async def test_expired_relationship_blocked(trust_iam_db: DatabaseEngine):
    principal_id, _ = await _seed_employed_principal(trust_iam_db, expires_at="2000-01-01T00:00:00Z")
    guard = PrivilegedSurfaceGuard(trust_iam_db)
    with pytest.raises(PrivilegedAccessDeniedError, match="EXPIRED"):
        await guard.authorize_privileged_operation(
            caller=_caller(principal_id),
            target_org_id="org_alpha",
            action=PrivilegedAction.CREATE_API_KEY,
            require_trust_admission=True,
        )


@pytest.mark.asyncio
async def test_conflicted_principal_blocked(trust_iam_db: DatabaseEngine):
    from responsibleai.db.engine import trust_fabric_principals

    dir_svc = PrincipalDirectory(trust_iam_db)
    person = await dir_svc.create_principal(
        org_id="org_alpha", principal_type=PrincipalType.HUMAN, display_name="Conflicted Person"
    )
    async with trust_iam_db.raw.begin() as conn:
        from sqlalchemy import update

        await conn.execute(
            update(trust_fabric_principals)
            .where(trust_fabric_principals.c.id == person.id)
            .values(lifecycle_state="CONFLICTED")
        )

    guard = PrivilegedSurfaceGuard(trust_iam_db)
    with pytest.raises(PrivilegedAccessDeniedError, match="CONFLICTED"):
        await guard.authorize_privileged_operation(
            caller=_caller(person.id),
            target_org_id="org_alpha",
            action=PrivilegedAction.CREATE_API_KEY,
            require_trust_admission=True,
        )


@pytest.mark.asyncio
async def test_cross_tenant_trust_decision_blocked(trust_iam_db: DatabaseEngine):
    """A principal proven employed in org_alpha must not gain admission when acting against org_beta."""
    principal_id, _ = await _seed_employed_principal(trust_iam_db, org_id="org_alpha")
    guard = PrivilegedSurfaceGuard(trust_iam_db)

    caller = PrivilegedCallerContext(principal_id=principal_id, org_id="org_beta", role=Role.ADMIN)
    with pytest.raises(PrivilegedAccessDeniedError):
        await guard.authorize_privileged_operation(
            caller=caller,
            target_org_id="org_beta",
            action=PrivilegedAction.CREATE_API_KEY,
            require_trust_admission=True,
        )


@pytest.mark.asyncio
async def test_wrong_principal_id_not_conflated(trust_iam_db: DatabaseEngine):
    """A trust-proven principal's PROVEN status must not leak to a different principal_id."""
    await _seed_employed_principal(trust_iam_db)
    guard = PrivilegedSurfaceGuard(trust_iam_db)
    with pytest.raises(PrivilegedAccessDeniedError, match="UNKNOWN"):
        await guard.authorize_privileged_operation(
            caller=_caller("some_other_unrelated_principal_id"),
            target_org_id="org_alpha",
            action=PrivilegedAction.CREATE_API_KEY,
            require_trust_admission=True,
        )


@pytest.mark.asyncio
async def test_stale_result_blocked_after_revocation(trust_iam_db: DatabaseEngine):
    """PROVEN -> revoke -> re-attempt with the same caller must re-evaluate fresh and BLOCK.

    The engine performs a live DB read on every call (no caching layer), so this also
    proves there is no caller-side or provider-side staleness window to exploit.
    """
    principal_id, rel_id = await _seed_employed_principal(trust_iam_db)
    guard = PrivilegedSurfaceGuard(trust_iam_db)

    # First call: PROVEN, allowed.
    res = await guard.authorize_privileged_operation(
        caller=_caller(principal_id),
        target_org_id="org_alpha",
        action=PrivilegedAction.CREATE_API_KEY,
        require_trust_admission=True,
    )
    assert res.allowed is True

    # Revoke the underlying relationship.
    auth_svc = AuthorityGraph(trust_iam_db)
    await auth_svc.revoke_relationship(rel_id, org_id="org_alpha")

    # Second call with the identical caller context must now be blocked.
    with pytest.raises(PrivilegedAccessDeniedError, match="REVOKED"):
        await guard.authorize_privileged_operation(
            caller=_caller(principal_id),
            target_org_id="org_alpha",
            action=PrivilegedAction.CREATE_API_KEY,
            require_trust_admission=True,
        )


@pytest.mark.asyncio
async def test_caller_supplied_proof_state_is_not_authoritative(trust_iam_db: DatabaseEngine):
    """context_data cannot be used to smuggle in a fabricated proof state; the engine is always consulted."""
    guard = PrivilegedSurfaceGuard(trust_iam_db)
    with pytest.raises(PrivilegedAccessDeniedError, match="UNKNOWN"):
        await guard.authorize_privileged_operation(
            caller=_caller("attacker_principal"),
            target_org_id="org_alpha",
            action=PrivilegedAction.CREATE_API_KEY,
            require_trust_admission=True,
            context_data={"proof_state": "PROVEN", "trust_status": "PROVEN"},
        )


@pytest.mark.asyncio
async def test_provider_unavailable_fails_closed(trust_iam_db: DatabaseEngine, monkeypatch):
    """If the trust evaluator raises, the privileged action must not proceed."""
    principal_id, _ = await _seed_employed_principal(trust_iam_db)
    guard = PrivilegedSurfaceGuard(trust_iam_db)

    async def _boom(*, principal_id, org_id):
        raise RuntimeError("trust provider unavailable")

    monkeypatch.setattr(guard.trust_proofs, "prove_employment", _boom)

    with pytest.raises(RuntimeError, match="trust provider unavailable"):
        await guard.authorize_privileged_operation(
            caller=_caller(principal_id),
            target_org_id="org_alpha",
            action=PrivilegedAction.CREATE_API_KEY,
            require_trust_admission=True,
        )


@pytest.mark.asyncio
async def test_proven_trust_does_not_bypass_role_check(trust_iam_db: DatabaseEngine):
    """A PROVEN trust result is a prerequisite only -- it must not itself grant privilege."""
    from responsibleai.iam.errors import PrivilegedAccessDeniedError as DeniedError

    principal_id, _ = await _seed_employed_principal(trust_iam_db)
    guard = PrivilegedSurfaceGuard(trust_iam_db)

    with pytest.raises(DeniedError, match="requires ADMIN or OWNER role"):
        await guard.authorize_privileged_operation(
            caller=_caller(principal_id, role=Role.VIEWER),
            target_org_id="org_alpha",
            action=PrivilegedAction.CREATE_API_KEY,
            require_trust_admission=True,
        )
