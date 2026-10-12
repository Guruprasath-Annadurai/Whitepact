# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for OrgRepository -- exercised only incidentally by other tests
before this file existed, leaving several branches (set_plan's optional
fields, get_org_by_slug/stripe_customer misses, authenticate's SSO/legacy
paths, MFA lifecycle) untested in isolation."""

from __future__ import annotations

import pytest

from responsibleai.db.engine import create_engine
from responsibleai.db.org_repository import OrgRepository, SSORequiredError, _plan_from_str
from responsibleai.rbac.models import Plan, Role


@pytest.fixture()
async def engine():
    e = create_engine(":memory:")
    await e.init()
    yield e
    await e.close()


@pytest.fixture()
def repo(engine):
    return OrgRepository(engine)


class TestCreateAndGetOrg:
    async def test_create_and_get_by_id(self, repo):
        org = await repo.create_org("Acme", "acme")
        fetched = await repo.get_org(org.id)
        assert fetched is not None
        assert fetched.name == "Acme"
        assert fetched.plan == Plan.FREE

    async def test_get_org_missing_returns_none(self, repo):
        assert await repo.get_org("nonexistent") is None

    async def test_get_org_by_slug(self, repo):
        org = await repo.create_org("Acme", "acme")
        fetched = await repo.get_org_by_slug("acme")
        assert fetched is not None
        assert fetched.id == org.id

    async def test_get_org_by_slug_missing_returns_none(self, repo):
        assert await repo.get_org_by_slug("nope") is None

    async def test_get_org_by_stripe_customer_missing_returns_none(self, repo):
        assert await repo.get_org_by_stripe_customer("cus_none") is None

    async def test_list_orgs(self, repo):
        await repo.create_org("A", "a")
        await repo.create_org("B", "b")
        orgs = await repo.list_orgs()
        assert len(orgs) == 2

    async def test_provisioner_binding_is_persisted_but_never_serialized(self, repo):
        org = await repo.create_org("Acme", "acme", provisioner_key_id="legacy:abc")
        fetched = await repo.get_org(org.id)
        assert fetched is not None
        assert fetched.provisioner_key_id == "legacy:abc"
        assert "provisioner_key_id" not in fetched.to_dict()

    async def test_delete_org_returns_true_when_found(self, repo):
        org = await repo.create_org("Acme", "acme")
        assert await repo.delete_org(org.id) is True
        assert await repo.get_org(org.id) is None

    async def test_delete_org_returns_false_when_missing(self, repo):
        assert await repo.delete_org("nonexistent") is False


class TestSetPlan:
    async def test_set_plan_only(self, repo):
        org = await repo.create_org("Acme", "acme")
        ok = await repo.set_plan(org.id, Plan.PRO)
        assert ok is True
        fetched = await repo.get_org(org.id)
        assert fetched.plan == Plan.PRO
        assert fetched.stripe_customer_id is None

    async def test_set_plan_with_all_optional_fields(self, repo):
        org = await repo.create_org("Acme", "acme")
        ok = await repo.set_plan(
            org.id,
            Plan.ENTERPRISE,
            stripe_customer_id="cus_1",
            stripe_subscription_id="sub_1",
            plan_renews_at="2027-01-01T00:00:00+00:00",
        )
        assert ok is True
        fetched = await repo.get_org(org.id)
        assert fetched.stripe_customer_id == "cus_1"
        assert fetched.stripe_subscription_id == "sub_1"
        assert fetched.plan_renews_at == "2027-01-01T00:00:00+00:00"

    async def test_set_plan_missing_org_returns_false(self, repo):
        assert await repo.set_plan("nonexistent", Plan.PRO) is False

    async def test_get_org_by_stripe_customer_found(self, repo):
        org = await repo.create_org("Acme", "acme")
        await repo.set_plan(org.id, Plan.PRO, stripe_customer_id="cus_42")
        fetched = await repo.get_org_by_stripe_customer("cus_42")
        assert fetched is not None
        assert fetched.id == org.id


class TestSsoRequired:
    async def test_enable_sso_required(self, repo):
        org = await repo.create_org("Acme", "acme")
        assert await repo.set_sso_required(org.id, True) is True
        fetched = await repo.get_org(org.id)
        assert fetched.sso_required is True

    async def test_disable_sso_required(self, repo):
        org = await repo.create_org("Acme", "acme")
        await repo.set_sso_required(org.id, True)
        await repo.set_sso_required(org.id, False)
        fetched = await repo.get_org(org.id)
        assert fetched.sso_required is False

    async def test_missing_org_returns_false(self, repo):
        assert await repo.set_sso_required("nonexistent", True) is False


class TestOrgMfaRequired:
    async def test_enable_and_disable(self, repo):
        org = await repo.create_org("Acme", "acme")
        assert await repo.set_org_mfa_required(org.id, True) is True
        assert (await repo.get_org(org.id)).mfa_required is True
        await repo.set_org_mfa_required(org.id, False)
        assert (await repo.get_org(org.id)).mfa_required is False


class TestApiKeys:
    async def test_create_and_list_keys(self, repo):
        org = await repo.create_org("Acme", "acme")
        key_rec, raw = await repo.create_key(org.id, "ci-key", role=Role.ADMIN)
        assert raw.startswith("rai_")
        keys = await repo.list_keys(org.id)
        assert len(keys) == 1
        assert keys[0].id == key_rec.id

    async def test_revoked_keys_excluded_from_list(self, repo):
        org = await repo.create_org("Acme", "acme")
        key_rec, _ = await repo.create_key(org.id, "ci-key")
        await repo.revoke_key(key_rec.id, org_id=org.id)
        assert await repo.list_keys(org.id) == []

    async def test_revoke_missing_key_returns_false(self, repo):
        assert await repo.revoke_key("nonexistent") is False

    async def test_get_key_found(self, repo):
        org = await repo.create_org("Acme", "acme")
        key_rec, _ = await repo.create_key(org.id, "ci-key")
        fetched = await repo.get_key(key_rec.id)
        assert fetched is not None
        assert fetched.name == "ci-key"

    async def test_get_key_missing_returns_none(self, repo):
        assert await repo.get_key("nonexistent") is None


class TestAuthenticate:
    async def test_valid_key_returns_context(self, repo):
        org = await repo.create_org("Acme", "acme")
        _key_rec, raw = await repo.create_key(org.id, "ci-key", role=Role.ANALYST)
        ctx = await repo.authenticate(raw)
        assert ctx is not None
        assert ctx.org_id == org.id
        assert ctx.org_name == "Acme"
        assert ctx.is_legacy is False
        assert ctx.plan == Plan.FREE

    async def test_invalid_key_returns_none(self, repo):
        assert await repo.authenticate("rai_not-a-real-key") is None

    async def test_revoked_key_returns_none(self, repo):
        org = await repo.create_org("Acme", "acme")
        key_rec, raw = await repo.create_key(org.id, "ci-key")
        await repo.revoke_key(key_rec.id, org_id=org.id)
        assert await repo.authenticate(raw) is None

    async def test_sso_required_org_raises(self, repo):
        org = await repo.create_org("Acme", "acme")
        _key_rec, raw = await repo.create_key(org.id, "ci-key")
        await repo.set_sso_required(org.id, True)
        with pytest.raises(SSORequiredError):
            await repo.authenticate(raw)

    async def test_updates_last_used_at(self, repo):
        org = await repo.create_org("Acme", "acme")
        key_rec, raw = await repo.create_key(org.id, "ci-key")
        await repo.authenticate(raw)
        fetched = await repo.get_key(key_rec.id)
        assert fetched.last_used_at is not None


class TestPlanFromStr:
    def test_valid_plan_string(self):
        assert _plan_from_str("pro") == Plan.PRO

    def test_none_defaults_to_free(self):
        assert _plan_from_str(None) == Plan.FREE

    def test_invalid_plan_string_falls_back_to_free(self):
        assert _plan_from_str("not-a-real-plan") == Plan.FREE


class TestAuthenticateLastUsedUpdateFailure:
    async def test_authenticate_still_succeeds_if_last_used_update_fails(self, repo, monkeypatch):
        org = await repo.create_org("Acme", "acme")
        _key_rec, raw = await repo.create_key(org.id, "ci-key")

        real_begin = type(repo._engine.raw).begin
        call_count = {"n": 0}

        def _flaky_begin(self, *args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("simulated DB failure")
            return real_begin(self, *args, **kwargs)

        monkeypatch.setattr(type(repo._engine.raw), "begin", _flaky_begin)
        ctx = await repo.authenticate(raw)
        assert ctx is not None
        assert ctx.org_id == org.id


class TestMfaLifecycle:
    async def test_set_confirm_and_disable_mfa(self, repo):
        org = await repo.create_org("Acme", "acme")
        key_rec, _raw = await repo.create_key(org.id, "ci-key")

        assert await repo.set_mfa_secret(key_rec.id, "SECRET123") is True
        fetched = await repo.get_key(key_rec.id)
        assert fetched.mfa_secret == "SECRET123"
        assert fetched.mfa_enrolled is False

        assert await repo.confirm_mfa(key_rec.id, ["hash1", "hash2"]) is True
        fetched = await repo.get_key(key_rec.id)
        assert fetched.mfa_enrolled is True
        assert fetched.mfa_backup_codes == ["hash1", "hash2"]

        assert await repo.consume_backup_code(key_rec.id, ["hash2"]) is True
        fetched = await repo.get_key(key_rec.id)
        assert fetched.mfa_backup_codes == ["hash2"]

        assert await repo.disable_mfa(key_rec.id) is True
        fetched = await repo.get_key(key_rec.id)
        assert fetched.mfa_enrolled is False
        assert fetched.mfa_secret is None
        assert fetched.mfa_backup_codes is None

    async def test_set_mfa_secret_missing_key_returns_false(self, repo):
        assert await repo.set_mfa_secret("nonexistent", "SECRET") is False

    async def test_confirm_mfa_missing_key_returns_false(self, repo):
        assert await repo.confirm_mfa("nonexistent", []) is False

    async def test_disable_mfa_missing_key_returns_false(self, repo):
        assert await repo.disable_mfa("nonexistent") is False

    async def test_consume_backup_code_missing_key_returns_false(self, repo):
        assert await repo.consume_backup_code("nonexistent", []) is False


class TestLastUsedRefreshIsThrottledButAuthorizationIsNot:
    """last_used_at is telemetry; revocation and expiry must still apply on every call."""

    @staticmethod
    def _count_writes(repo, monkeypatch) -> dict[str, int]:
        real_begin = type(repo._engine.raw).begin
        calls = {"n": 0}

        def _counting_begin(self, *args, **kwargs):
            calls["n"] += 1
            return real_begin(self, *args, **kwargs)

        monkeypatch.setattr(type(repo._engine.raw), "begin", _counting_begin)
        return calls

    async def test_repeat_calls_inside_the_interval_do_not_write(self, repo, monkeypatch):
        org = await repo.create_org("Acme", "acme")
        _rec, raw = await repo.create_key(org.id, "ci-key")
        calls = self._count_writes(repo, monkeypatch)
        for _ in range(5):
            assert await repo.authenticate(raw) is not None
        assert calls["n"] == 1, "only the first use should write last_used_at"

    async def test_a_stale_value_is_refreshed(self, repo, monkeypatch):
        from datetime import UTC, datetime, timedelta

        from sqlalchemy import update

        from responsibleai.db.engine import org_api_keys
        from responsibleai.db.org_repository import LAST_USED_REFRESH_SECONDS

        org = await repo.create_org("Acme", "acme")
        rec, raw = await repo.create_key(org.id, "ci-key")
        stale = (datetime.now(UTC) - timedelta(seconds=LAST_USED_REFRESH_SECONDS + 5)).isoformat()
        async with repo._engine.raw.begin() as conn:
            await conn.execute(
                update(org_api_keys).where(org_api_keys.c.id == rec.id).values(last_used_at=stale)
            )
        calls = self._count_writes(repo, monkeypatch)
        await repo.authenticate(raw)
        assert calls["n"] == 1
        assert (await repo.get_key(rec.id)).last_used_at > stale

    async def test_revocation_is_enforced_immediately_despite_throttling(self, repo):
        org = await repo.create_org("Acme", "acme")
        rec, raw = await repo.create_key(org.id, "ci-key")
        assert await repo.authenticate(raw) is not None  # warms last_used_at
        assert await repo.revoke_key(rec.id, org_id=org.id) is True
        assert await repo.authenticate(raw) is None

    @pytest.mark.parametrize("bad", [None, "", "not-a-date", "2020-13-45T99:99:99"])
    def test_unparseable_last_used_counts_as_stale(self, bad):
        from responsibleai.db.org_repository import _last_used_is_stale

        assert _last_used_is_stale(bad) is True
