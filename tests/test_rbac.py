"""Unit tests for the RBAC module — roles, permissions, models."""

from __future__ import annotations

from responsibleai.rbac.models import AuditEntry, Organization, OrgApiKey, OrgContext, Plan, Role
from responsibleai.rbac.permissions import has_permission, has_plan, role_from_str, roles_above

# ── Role hierarchy ─────────────────────────────────────────────────────────────

class TestRoleHierarchy:
    def test_owner_has_all_permissions(self):
        for role in Role:
            assert has_permission(Role.OWNER, role)

    def test_viewer_has_only_viewer(self):
        assert has_permission(Role.VIEWER, Role.VIEWER)
        assert not has_permission(Role.VIEWER, Role.ANALYST)
        assert not has_permission(Role.VIEWER, Role.ADMIN)
        assert not has_permission(Role.VIEWER, Role.OWNER)

    def test_analyst_has_analyst_and_viewer(self):
        assert has_permission(Role.ANALYST, Role.VIEWER)
        assert has_permission(Role.ANALYST, Role.ANALYST)
        assert not has_permission(Role.ANALYST, Role.ADMIN)
        assert not has_permission(Role.ANALYST, Role.OWNER)

    def test_admin_has_all_except_owner(self):
        assert has_permission(Role.ADMIN, Role.VIEWER)
        assert has_permission(Role.ADMIN, Role.ANALYST)
        assert has_permission(Role.ADMIN, Role.ADMIN)
        assert not has_permission(Role.ADMIN, Role.OWNER)

    def test_reflexive(self):
        for role in Role:
            assert has_permission(role, role)

    def test_roles_above_viewer(self):
        above = roles_above(Role.VIEWER)
        assert all(r in above for r in Role)

    def test_roles_above_owner(self):
        above = roles_above(Role.OWNER)
        assert above == [Role.OWNER]

    def test_roles_above_analyst(self):
        above = roles_above(Role.ANALYST)
        assert Role.ANALYST in above
        assert Role.ADMIN in above
        assert Role.OWNER in above
        assert Role.VIEWER not in above


# ── Plan hierarchy ───────────────────────────────────────────────────────────────

class TestPlanHierarchy:
    def test_enterprise_satisfies_everything(self):
        for plan in Plan:
            assert has_plan(Plan.ENTERPRISE, plan)

    def test_free_satisfies_only_free(self):
        assert has_plan(Plan.FREE, Plan.FREE)
        assert not has_plan(Plan.FREE, Plan.PRO)
        assert not has_plan(Plan.FREE, Plan.ENTERPRISE)

    def test_pro_satisfies_free_and_pro_not_enterprise(self):
        assert has_plan(Plan.PRO, Plan.FREE)
        assert has_plan(Plan.PRO, Plan.PRO)
        assert not has_plan(Plan.PRO, Plan.ENTERPRISE)


# ── role_from_str ──────────────────────────────────────────────────────────────

class TestRoleFromStr:
    def test_valid_upper(self):
        assert role_from_str("OWNER") == Role.OWNER

    def test_valid_lower(self):
        assert role_from_str("analyst") == Role.ANALYST

    def test_valid_mixed(self):
        assert role_from_str("Admin") == Role.ADMIN

    def test_invalid_defaults_to_viewer(self):
        assert role_from_str("superuser") == Role.VIEWER

    def test_empty_defaults_to_viewer(self):
        assert role_from_str("") == Role.VIEWER


# ── Organization model ─────────────────────────────────────────────────────────

class TestOrganization:
    def test_to_dict_keys(self):
        org = Organization(name="Acme", slug="acme", created_at="2026-01-01T00:00:00Z")
        d = org.to_dict()
        assert {"id", "name", "slug", "monthly_budget_usd", "created_at"} <= d.keys()

    def test_default_budget(self):
        org = Organization(name="X", slug="x")
        assert org.monthly_budget_usd == 10_000.0

    def test_id_auto_generated(self):
        o1 = Organization(name="A", slug="a")
        o2 = Organization(name="B", slug="b")
        assert o1.id != o2.id


# ── OrgApiKey model ────────────────────────────────────────────────────────────

class TestOrgApiKey:
    def test_to_dict_no_raw_key(self):
        k = OrgApiKey(org_id="org1", name="ci-key", role=Role.ANALYST)
        d = k.to_dict()
        assert "key" not in d
        assert d["role"] == "ANALYST"

    def test_to_dict_with_raw_key(self):
        k = OrgApiKey(org_id="org1", name="ci-key", role=Role.ANALYST)
        d = k.to_dict(include_key="rai_abc123")
        assert d["key"] == "rai_abc123"

    def test_revoked_defaults_false(self):
        k = OrgApiKey(org_id="x", name="k", role=Role.VIEWER)
        assert k.revoked is False


# ── OrgContext ─────────────────────────────────────────────────────────────────

class TestOrgContext:
    def test_legacy_context(self):
        ctx = OrgContext(key_id="legacy", role=Role.OWNER, is_legacy=True)
        assert ctx.is_legacy is True
        assert ctx.org_id is None

    def test_org_context(self):
        ctx = OrgContext(key_id="k1", role=Role.ANALYST, org_id="org1", org_name="Acme")
        assert ctx.org_id == "org1"
        assert ctx.org_name == "Acme"
        assert ctx.is_legacy is False


# ── AuditEntry ─────────────────────────────────────────────────────────────────

class TestAuditEntry:
    def test_to_dict_keys(self):
        entry = AuditEntry(endpoint="/api/evaluate", method="POST")
        d = entry.to_dict()
        expected = {"id", "timestamp", "org_id", "key_id", "endpoint",
                    "method", "status_code", "ip_address", "request_id", "duration_ms"}
        assert expected <= d.keys()

    def test_id_auto_generated(self):
        e1 = AuditEntry(endpoint="/a", method="GET")
        e2 = AuditEntry(endpoint="/b", method="POST")
        assert e1.id != e2.id
