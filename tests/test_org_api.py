"""Tests for OrgRepository — multi-tenant org and API key management."""

from __future__ import annotations

import pytest

from responsibleai.db.engine import create_engine
from responsibleai.db.org_repository import (
    OrgRepository,
    SSORequiredError,
    _generate_raw_key,
    _hash_key,
)
from responsibleai.rbac.models import Role


@pytest.fixture()
async def db():
    engine = create_engine(":memory:")
    await engine.init()
    yield engine
    await engine.close()


@pytest.fixture()
async def repo(db):
    return OrgRepository(db)


@pytest.fixture()
async def org(repo):
    return await repo.create_org("Acme Corp", "acme", monthly_budget_usd=5_000.0)


# ── Organization CRUD ─────────────────────────────────────────────────────────

class TestOrganizationCRUD:
    async def test_create_org_returns_org(self, repo):
        org = await repo.create_org("Test Inc", "test-inc")
        assert org.name == "Test Inc"
        assert org.slug == "test-inc"
        assert org.id

    async def test_create_org_sets_budget(self, repo):
        org = await repo.create_org("Budget Co", "budget-co", monthly_budget_usd=2500.0)
        assert org.monthly_budget_usd == 2500.0

    async def test_get_org_by_id(self, repo, org):
        fetched = await repo.get_org(org.id)
        assert fetched is not None
        assert fetched.id == org.id
        assert fetched.name == "Acme Corp"

    async def test_get_org_missing_returns_none(self, repo):
        assert await repo.get_org("nonexistent-id") is None

    async def test_get_org_by_slug(self, repo, org):
        fetched = await repo.get_org_by_slug("acme")
        assert fetched is not None
        assert fetched.id == org.id

    async def test_get_org_by_slug_missing(self, repo):
        assert await repo.get_org_by_slug("does-not-exist") is None

    async def test_list_orgs_empty(self, repo):
        assert await repo.list_orgs() == []

    async def test_list_orgs_multiple(self, repo):
        await repo.create_org("A", "a")
        await repo.create_org("B", "b")
        orgs = await repo.list_orgs()
        assert len(orgs) == 2

    async def test_delete_org_returns_true(self, repo, org):
        deleted = await repo.delete_org(org.id)
        assert deleted is True
        assert await repo.get_org(org.id) is None

    async def test_delete_missing_org_returns_false(self, repo):
        assert await repo.delete_org("ghost") is False

    async def test_created_at_populated(self, repo):
        org = await repo.create_org("Time Corp", "time-corp")
        assert org.created_at


# ── API Key management ─────────────────────────────────────────────────────────

class TestApiKeyManagement:
    async def test_create_key_returns_tuple(self, repo, org):
        key_rec, raw = await repo.create_key(org.id, "ci-key", Role.ANALYST)
        assert key_rec.id
        assert raw.startswith("rai_")
        assert len(raw) > 10

    async def test_create_key_role_stored(self, repo, org):
        key_rec, _ = await repo.create_key(org.id, "admin-key", Role.ADMIN)
        assert key_rec.role == Role.ADMIN

    async def test_raw_key_unique_each_call(self, repo, org):
        _, raw1 = await repo.create_key(org.id, "k1", Role.ANALYST)
        _, raw2 = await repo.create_key(org.id, "k2", Role.ANALYST)
        assert raw1 != raw2

    async def test_list_keys_empty(self, repo, org):
        assert await repo.list_keys(org.id) == []

    async def test_list_keys_returns_active(self, repo, org):
        await repo.create_key(org.id, "k1", Role.VIEWER)
        await repo.create_key(org.id, "k2", Role.ANALYST)
        keys = await repo.list_keys(org.id)
        assert len(keys) == 2

    async def test_list_keys_excludes_revoked(self, repo, org):
        key_rec, _ = await repo.create_key(org.id, "k1", Role.VIEWER)
        await repo.revoke_key(key_rec.id)
        keys = await repo.list_keys(org.id)
        assert len(keys) == 0

    async def test_revoke_key_returns_true(self, repo, org):
        key_rec, _ = await repo.create_key(org.id, "k", Role.ANALYST)
        assert await repo.revoke_key(key_rec.id) is True

    async def test_revoke_missing_key_returns_false(self, repo):
        assert await repo.revoke_key("missing-key-id") is False

    async def test_key_created_at_populated(self, repo, org):
        key_rec, _ = await repo.create_key(org.id, "k", Role.ANALYST)
        assert key_rec.created_at


# ── Authentication ─────────────────────────────────────────────────────────────

class TestAuthentication:
    async def test_authenticate_valid_key(self, repo, org):
        _, raw = await repo.create_key(org.id, "app-key", Role.ANALYST)
        ctx = await repo.authenticate(raw)
        assert ctx is not None
        assert ctx.org_id == org.id
        assert ctx.role == Role.ANALYST
        assert ctx.is_legacy is False

    async def test_authenticate_returns_none_for_invalid(self, repo):
        ctx = await repo.authenticate("rai_fakekeyvalue12345")
        assert ctx is None

    async def test_authenticate_revoked_key_returns_none(self, repo, org):
        key_rec, raw = await repo.create_key(org.id, "k", Role.ANALYST)
        await repo.revoke_key(key_rec.id)
        assert await repo.authenticate(raw) is None

    async def test_authenticate_sets_org_name(self, repo, org):
        _, raw = await repo.create_key(org.id, "k", Role.VIEWER)
        ctx = await repo.authenticate(raw)
        assert ctx.org_name == "Acme Corp"

    async def test_authenticate_owner_key(self, repo, org):
        _, raw = await repo.create_key(org.id, "owner-key", Role.OWNER)
        ctx = await repo.authenticate(raw)
        assert ctx.role == Role.OWNER

    async def test_hash_key_is_deterministic(self):
        raw = _generate_raw_key()
        assert _hash_key(raw) == _hash_key(raw)

    async def test_different_keys_have_different_hashes(self):
        assert _hash_key("key1") != _hash_key("key2")

    async def test_authenticate_updates_last_used(self, repo, org):
        _, raw = await repo.create_key(org.id, "k", Role.ANALYST)
        await repo.authenticate(raw)
        keys = await repo.list_keys(org.id)
        assert keys[0].last_used_at is not None


# ── SSO enforcement ──────────────────────────────────────────────────────────────

class TestSSOEnforcement:
    async def test_org_sso_required_defaults_false(self, org):
        assert org.sso_required is False

    async def test_set_sso_required_true(self, repo, org):
        updated = await repo.set_sso_required(org.id, True)
        assert updated is True
        fetched = await repo.get_org(org.id)
        assert fetched.sso_required is True

    async def test_set_sso_required_false(self, repo, org):
        await repo.set_sso_required(org.id, True)
        await repo.set_sso_required(org.id, False)
        fetched = await repo.get_org(org.id)
        assert fetched.sso_required is False

    async def test_set_sso_required_missing_org_returns_false(self, repo):
        assert await repo.set_sso_required("nonexistent", True) is False

    async def test_authenticate_blocked_when_sso_required(self, repo, org):
        _, raw = await repo.create_key(org.id, "app-key", Role.ANALYST)
        await repo.set_sso_required(org.id, True)
        with pytest.raises(SSORequiredError) as exc_info:
            await repo.authenticate(raw)
        assert exc_info.value.org_id == org.id

    async def test_authenticate_works_after_sso_disabled_again(self, repo, org):
        _, raw = await repo.create_key(org.id, "app-key", Role.ANALYST)
        await repo.set_sso_required(org.id, True)
        await repo.set_sso_required(org.id, False)
        ctx = await repo.authenticate(raw)
        assert ctx is not None
        assert ctx.org_id == org.id

    async def test_sso_required_does_not_affect_other_orgs(self, repo, org):
        other = await repo.create_org("Other Co", "other-co")
        _, raw_other = await repo.create_key(other.id, "k", Role.ANALYST)
        await repo.set_sso_required(org.id, True)
        ctx = await repo.authenticate(raw_other)
        assert ctx is not None
        assert ctx.org_id == other.id
