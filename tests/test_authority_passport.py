# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for Authority Passport (Authority Everywhere Phase 5) --
`governance/authority_passport.py`'s `AuthorityPassport`,
`build_authority_passport_from_ceiling()`/`build_authority_passport_from_delegation()`,
`verify_passport()`, and `db/authority_passport_repository.py`'s
`AuthorityPassportRepository`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from responsibleai.db import AuthorityPassportRepository, create_engine
from responsibleai.governance.authority_passport import (
    AuthorityPassport,
    PassportStatus,
    build_authority_passport_from_ceiling,
    build_authority_passport_from_delegation,
    verify_passport,
)
from responsibleai.governance.ceiling import OrgAuthorityCeiling
from responsibleai.governance.delegation import DelegationRecord


def _ceiling(**kwargs) -> OrgAuthorityCeiling:
    defaults: dict = {"org_id": "org-1"}
    defaults.update(kwargs)
    return OrgAuthorityCeiling(**defaults)


def _delegation(**kwargs) -> DelegationRecord:
    defaults: dict = {
        "delegation_id": "del-1",
        "org_id": "org-1",
        "from_identity_id": None,
        "to_identity_id": "agent-1",
        "granted_action_types": frozenset({"rai_scan"}),
        "constraints": {},
        "require_approval_for": frozenset(),
        "purpose": "test",
        "granted_by": "admin-1",
        "granted_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return DelegationRecord(**defaults)


class TestIsActive:
    def test_active_by_default(self) -> None:
        passport = build_authority_passport_from_ceiling(_ceiling(), "agent-1")
        assert passport.is_active() is True

    def test_revoked_is_inactive(self) -> None:
        passport = AuthorityPassport(
            organization_id="org-1",
            principal_id="agent-1",
            source="org_ceiling",
            source_id="org-1",
            granted_action_types=(),
            revoked_at=datetime.now(UTC),
        )
        assert passport.is_active() is False

    def test_expired_is_inactive(self) -> None:
        past = datetime.now(UTC) - timedelta(minutes=1)
        passport = build_authority_passport_from_ceiling(_ceiling(), "agent-1", expires_at=past)
        assert passport.is_active() is False

    def test_not_yet_expired_is_active(self) -> None:
        future = datetime.now(UTC) + timedelta(hours=1)
        passport = build_authority_passport_from_ceiling(_ceiling(), "agent-1", expires_at=future)
        assert passport.is_active() is True


class TestBuildFromCeiling:
    def test_basic_fields(self) -> None:
        ceiling = _ceiling(
            max_value_usd=500,
            allowed_targets=["read_*"],
            denied_targets=["admin_*"],
            allowed_action_types=["rai_scan"],
            max_delegation_depth=2,
            require_approval_for=frozenset({"deployment"}),
        )
        passport = build_authority_passport_from_ceiling(ceiling, "agent-1")
        assert passport.organization_id == "org-1"
        assert passport.principal_id == "agent-1"
        assert passport.source == "org_ceiling"
        assert passport.source_id == "org-1"
        assert passport.granted_action_types == ("rai_scan",)
        assert passport.max_value_usd == 500
        assert passport.allowed_targets == ("read_*",)
        assert passport.denied_targets == ("admin_*",)
        assert passport.max_delegation_depth == 2
        assert passport.require_approval_for == ("deployment",)

    def test_unset_allowed_action_types_means_empty_grant(self) -> None:
        """Unlike OrgAuthorityCeiling.to_authority_context() (which
        synthesizes a single-action grant from the action being
        evaluated), a passport has no such action to synthesize from."""
        passport = build_authority_passport_from_ceiling(_ceiling(), "agent-1")
        assert passport.granted_action_types == ()

    def test_to_authority_context(self) -> None:
        ceiling = _ceiling(max_value_usd=500, allowed_action_types=["rai_scan"])
        passport = build_authority_passport_from_ceiling(ceiling, "agent-1")
        authority = passport.to_authority_context()
        assert authority.permits("rai_scan") is True
        assert authority.constraints["max_value_usd"] == 500


class TestBuildFromDelegation:
    def test_basic_fields(self) -> None:
        delegation = _delegation(
            constraints={"max_value_usd": 100, "allowed_targets": ["a"]},
            require_approval_for=frozenset({"deployment"}),
        )
        passport = build_authority_passport_from_delegation(delegation)
        assert passport.organization_id == "org-1"
        assert passport.principal_id == "agent-1"
        assert passport.source == "delegation"
        assert passport.source_id == "del-1"
        assert passport.granted_action_types == ("rai_scan",)
        assert passport.max_value_usd == 100
        assert passport.allowed_targets == ("a",)
        assert passport.require_approval_for == ("deployment",)

    def test_inherits_delegation_expiry_when_not_overridden(self) -> None:
        expiry = datetime.now(UTC) + timedelta(hours=2)
        delegation = _delegation(expires_at=expiry)
        passport = build_authority_passport_from_delegation(delegation)
        assert passport.expires_at == expiry

    def test_explicit_expiry_overrides_delegation_expiry(self) -> None:
        delegation_expiry = datetime.now(UTC) + timedelta(hours=2)
        override = datetime.now(UTC) + timedelta(minutes=30)
        delegation = _delegation(expires_at=delegation_expiry)
        passport = build_authority_passport_from_delegation(delegation, expires_at=override)
        assert passport.expires_at == override


class TestVerifyPassport:
    def test_revoked_passport_is_revoked(self) -> None:
        passport = AuthorityPassport(
            organization_id="org-1",
            principal_id="agent-1",
            source="org_ceiling",
            source_id="org-1",
            granted_action_types=(),
            revoked_at=datetime.now(UTC),
        )
        result = verify_passport(passport, ceiling=_ceiling())
        assert result.status == PassportStatus.REVOKED

    def test_expired_passport_is_expired(self) -> None:
        past = datetime.now(UTC) - timedelta(minutes=1)
        passport = build_authority_passport_from_ceiling(_ceiling(), "agent-1", expires_at=past)
        result = verify_passport(passport, ceiling=_ceiling())
        assert result.status == PassportStatus.EXPIRED

    def test_ceiling_source_matching_is_valid(self) -> None:
        ceiling = _ceiling(max_value_usd=500)
        passport = build_authority_passport_from_ceiling(ceiling, "agent-1")
        result = verify_passport(passport, ceiling=ceiling)
        assert result.status == PassportStatus.VALID

    def test_ceiling_source_missing_is_source_not_found(self) -> None:
        ceiling = _ceiling(max_value_usd=500)
        passport = build_authority_passport_from_ceiling(ceiling, "agent-1")
        result = verify_passport(passport, ceiling=None)
        assert result.status == PassportStatus.SOURCE_NOT_FOUND

    def test_ceiling_source_drifted_is_drifted(self) -> None:
        original = _ceiling(max_value_usd=500)
        passport = build_authority_passport_from_ceiling(original, "agent-1")
        changed = _ceiling(max_value_usd=100)  # admin narrowed the ceiling since issuance
        result = verify_passport(passport, ceiling=changed)
        assert result.status == PassportStatus.DRIFTED

    def test_delegation_source_matching_is_valid(self) -> None:
        delegation = _delegation(constraints={"max_value_usd": 100})
        passport = build_authority_passport_from_delegation(delegation)
        result = verify_passport(passport, delegation=delegation)
        assert result.status == PassportStatus.VALID

    def test_delegation_source_revoked_is_source_not_found(self) -> None:
        delegation = _delegation(constraints={"max_value_usd": 100})
        passport = build_authority_passport_from_delegation(delegation)
        revoked = _delegation(
            constraints={"max_value_usd": 100},
            revoked_at=datetime.now(UTC),
            revoked_by="admin-1",
        )
        result = verify_passport(passport, delegation=revoked)
        assert result.status == PassportStatus.SOURCE_NOT_FOUND

    def test_delegation_source_drifted_is_drifted(self) -> None:
        original = _delegation(constraints={"max_value_usd": 100})
        passport = build_authority_passport_from_delegation(original)
        changed = _delegation(constraints={"max_value_usd": 999})
        result = verify_passport(passport, delegation=changed)
        assert result.status == PassportStatus.DRIFTED

    def test_to_dict_shape(self) -> None:
        passport = build_authority_passport_from_ceiling(_ceiling(max_value_usd=100), "agent-1")
        d = passport.to_dict()
        assert d["organization_id"] == "org-1"
        assert d["principal_id"] == "agent-1"
        assert d["source"] == "org_ceiling"
        assert d["max_value_usd"] == 100
        assert d["revoked_at"] is None


class TestAuthorityPassportRepository:
    async def _engine(self):
        engine = create_engine(":memory:")
        await engine.init()
        return engine

    async def test_issue_and_get(self) -> None:
        engine = await self._engine()
        try:
            repo = AuthorityPassportRepository(engine)
            passport = build_authority_passport_from_ceiling(_ceiling(max_value_usd=500), "agent-1")
            await repo.issue(passport)
            fetched = await repo.get(passport.passport_id)
            assert fetched is not None
            assert fetched.max_value_usd == 500
            assert fetched.principal_id == "agent-1"
        finally:
            await engine.close()

    async def test_get_active_for_principal_latest_wins(self) -> None:
        engine = await self._engine()
        try:
            repo = AuthorityPassportRepository(engine)
            older = build_authority_passport_from_ceiling(_ceiling(max_value_usd=100), "agent-1")
            await repo.issue(older)
            newer = build_authority_passport_from_ceiling(_ceiling(max_value_usd=200), "agent-1")
            await repo.issue(newer)
            active = await repo.get_active_for_principal("org-1", "agent-1")
            assert active is not None
            assert active.max_value_usd == 200
        finally:
            await engine.close()

    async def test_no_passport_returns_none(self) -> None:
        engine = await self._engine()
        try:
            repo = AuthorityPassportRepository(engine)
            assert await repo.get_active_for_principal("org-1", "unknown") is None
        finally:
            await engine.close()

    async def test_revoke(self) -> None:
        engine = await self._engine()
        try:
            repo = AuthorityPassportRepository(engine)
            passport = build_authority_passport_from_ceiling(_ceiling(), "agent-1")
            await repo.issue(passport)
            revoked = await repo.revoke(
                passport.passport_id, revoked_by="admin-1", reason="rotated"
            )
            assert revoked.revoked_at is not None
            assert revoked.revoked_by == "admin-1"
            assert revoked.revoke_reason == "rotated"
            active = await repo.get_active_for_principal("org-1", "agent-1")
            assert active is None
        finally:
            await engine.close()

    async def test_revoke_unknown_raises(self) -> None:
        from responsibleai.db import AuthorityPassportNotFoundError

        engine = await self._engine()
        try:
            repo = AuthorityPassportRepository(engine)
            try:
                await repo.revoke("does-not-exist", revoked_by="admin-1")
                raise AssertionError("expected AuthorityPassportNotFoundError")
            except AuthorityPassportNotFoundError:
                pass
        finally:
            await engine.close()
