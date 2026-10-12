# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tiered policy governance (REC-25 option C) over real HTTP.

The mode is OFF by default (``single_admin``); these tests switch it on to prove the controls work before
anyone decides to activate them. Every refusal test reads the policy back: the rule set must be unchanged.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient

import responsibleai.dashboard.app as app_module
from tests import step_up_helpers as helpers
from tests import test_auth_canonical_seams as _seams
from tests.test_auth_canonical_seams import _get_step_up_detail, _onboard_org, _register_and_login

web_client = _seams.web_client
PASSWORD = "Correct-Horse-42!"
APPROVAL = "X-Policy-Change-Approval"


@pytest.fixture(autouse=True)
def _roomy_signup_window(monkeypatch):
    from responsibleai.dashboard.signup_guard import SignupRateWindow

    monkeypatch.setattr(
        app_module, "_signup_window", SignupRateWindow(max_per_window=1000, window_seconds=3600.0)
    )


def _engine():
    return app_module._ready(app_module._db_engine)


async def _login(client: AsyncClient, email: str) -> str:
    response = await client.post(
        "/api/v1/web/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return client.cookies["wp_csrf"]


class Org:
    """An owner and an administrator in one organization, each with a real enrolled TOTP factor."""

    def __init__(self, client: AsyncClient) -> None:
        self.client = client

    async def setup(self, tag: str) -> Org:
        c = self.client
        self.owner_email, self.admin_email = f"{tag}_o@example.com", f"{tag}_a@example.com"
        self.owner_id, _, csrf = await _register_and_login(c, f"{tag} O", self.owner_email)
        self.org_id = await _onboard_org(c, csrf, f"{tag} Inc")
        self.admin_id, _, _ = await _register_and_login(c, f"{tag} A", self.admin_email)
        csrf = await _login(c, self.owner_email)
        invite = await c.post(
            "/api/web/invitations",
            headers={"X-WP-CSRF": csrf},
            json={"email": self.admin_email, "role": "ADMIN"},
        )
        assert invite.status_code == 202, invite.text
        token = parse_qs(urlparse(invite.json()["invitation_url"]).query)["token"][0]
        admin_csrf = await _login(c, self.admin_email)
        accepted = await c.post(
            "/api/web/invitations/accept", headers={"X-WP-CSRF": admin_csrf}, json={"token": token}
        )
        assert accepted.status_code == 200, accepted.text
        self.owner_secret = await helpers.enroll_human_mfa(_engine(), self.owner_id)
        self.admin_secret = await helpers.enroll_human_mfa(_engine(), self.admin_id)
        return self

    async def as_owner(self) -> str:
        return await _login(self.client, self.owner_email)

    async def as_admin(self) -> str:
        return await _login(self.client, self.admin_email)

    async def rules(self) -> list[str]:
        csrf = self.client.cookies["wp_csrf"]
        response = await self.client.get("/api/v1/web/policy", headers={"X-WP-CSRF": csrf})
        assert response.status_code == 200, response.text
        return [r["rule_id"] for r in response.json()["rules"]]

    async def step_up_headers(self, csrf: str, secret: str, path_call) -> dict[str, str]:
        """Obtain a challenge by making the call unauthenticated, then answer it with a real code."""
        challenge = await path_call({"X-WP-CSRF": csrf})
        assert challenge.status_code == 403, challenge.text
        detail = _get_step_up_detail(challenge)
        assert detail["error"] == "step_up_required", detail
        return {
            "X-WP-CSRF": csrf,
            "X-Step-Up-Nonce": detail["required_nonce"],
            "X-Step-Up-Method": "mfa_totp",
            "X-Step-Up-Token": helpers.TIMELINE.code(secret),
        }


def _add_body(rule_id: str, effect: str, action: str) -> dict:
    return {
        "rule_id": rule_id,
        "reason_code": rule_id.upper(),
        "effect": effect,
        "action_types": [action],
    }


@pytest.fixture
async def org(web_client, monkeypatch):
    monkeypatch.setattr(app_module.settings, "policy_governance_mode", "tiered")
    return await Org(web_client).setup("tier")


async def _add(client, csrf_or_headers, body, **extra):
    headers = (
        csrf_or_headers if isinstance(csrf_or_headers, dict) else {"X-WP-CSRF": csrf_or_headers}
    )
    return await client.post("/api/v1/web/policy/rules", headers={**headers, **extra}, json=body)


async def test_single_admin_mode_is_unchanged_and_the_tiered_endpoints_are_inert(
    web_client, monkeypatch
) -> None:
    monkeypatch.setattr(app_module.settings, "policy_governance_mode", "single_admin")
    o = await Org(web_client).setup("single")
    csrf = await o.as_owner()
    assert (
        await _add(web_client, csrf, _add_body("a", "ALLOW", "x"))
    ).status_code == 200  # loosening, alone
    propose = await web_client.post(
        "/api/v1/web/policy/changes/propose",
        headers={"X-WP-CSRF": csrf},
        json={"operation": "remove", "rule_id": "a"},
    )
    assert propose.status_code == 409 and "not active" in propose.text


async def test_tightening_needs_one_administrator_only(org: Org) -> None:
    csrf = await org.as_owner()
    assert (await _add(org.client, csrf, _add_body("deny-x", "DENY", "x"))).status_code == 200
    assert (
        await _add(org.client, csrf, _add_body("review-y", "REQUIRE_APPROVAL", "y"))
    ).status_code == 200
    assert await org.rules() == ["deny-x", "review-y"]


async def test_loosening_without_an_approval_is_refused_and_changes_nothing(org: Org) -> None:
    csrf = await org.as_owner()
    await _add(org.client, csrf, _add_body("deny-x", "DENY", "x"))
    removed = await org.client.delete(
        "/api/v1/web/policy/rules/deny-x", headers={"X-WP-CSRF": csrf}
    )
    assert removed.status_code == 403, removed.text
    detail = _get_step_up_detail(removed)
    assert detail["error"] == "policy_change_approval_required" and detail["change_digest"]
    allow = await _add(org.client, csrf, _add_body("allow-z", "ALLOW", "z"))
    assert allow.status_code == 403
    assert await org.rules() == ["deny-x"]


async def _propose(org: Org, body: dict) -> dict:
    csrf = await org.as_owner()
    proposal = await org.client.post(
        "/api/v1/web/policy/changes/propose", headers={"X-WP-CSRF": csrf}, json=body
    )
    assert proposal.status_code == 200, proposal.text
    return proposal.json()


async def _approve(org: Org, approval_id: str):
    csrf = await org.as_admin()

    async def call(headers):
        return await org.client.post(
            f"/api/v1/web/policy/changes/{approval_id}/approve", headers=headers
        )

    headers = await org.step_up_headers(csrf, org.admin_secret, call)
    return await call(headers)


async def _execute_removal(org: Org, rule_id: str, approval_id: str, *, secret=None, csrf=None):
    csrf = csrf or await org.as_owner()

    async def call(headers):
        return await org.client.delete(
            f"/api/v1/web/policy/rules/{rule_id}", headers={**headers, APPROVAL: approval_id}
        )

    # With an approval header present the route asks for step-up next.
    headers = await org.step_up_headers(csrf, secret or org.owner_secret, call)
    return await call(headers)


async def test_a_loosening_edit_succeeds_only_with_a_distinct_approver_and_step_up(
    org: Org,
) -> None:
    csrf = await org.as_owner()
    await _add(org.client, csrf, _add_body("deny-x", "DENY", "x"))
    proposal = await _propose(org, {"operation": "remove", "rule_id": "deny-x"})
    approved = await _approve(org, proposal["approval_id"])
    assert approved.status_code == 200, approved.text
    done = await _execute_removal(org, "deny-x", proposal["approval_id"])
    assert done.status_code == 200, done.text
    assert await org.rules() == []
    # The approval is spent: the same approval cannot remove another rule or repeat the edit.
    await _add(org.client, await org.as_owner(), _add_body("deny-x", "DENY", "x"))
    again = await _execute_removal(org, "deny-x", proposal["approval_id"])
    assert again.status_code == 403, again.text
    assert await org.rules() == ["deny-x"]
    # The history says who did what: owner made every change; approver is recorded in the approval.
    history = (
        await org.client.get(
            "/api/v1/web/policy/history", headers={"X-WP-CSRF": org.client.cookies["wp_csrf"]}
        )
    ).json()
    assert history["chain_valid"] is True


async def test_the_requester_cannot_approve_their_own_loosening(org: Org) -> None:
    csrf = await org.as_owner()
    await _add(org.client, csrf, _add_body("deny-x", "DENY", "x"))
    proposal = await _propose(org, {"operation": "remove", "rule_id": "deny-x"})
    owner_csrf = await org.as_owner()

    async def call(headers):
        return await org.client.post(
            f"/api/v1/web/policy/changes/{proposal['approval_id']}/approve", headers=headers
        )

    headers = await org.step_up_headers(owner_csrf, org.owner_secret, call)
    self_approved = await call(headers)
    assert self_approved.status_code == 403, self_approved.text
    unapproved = await _execute_removal(org, "deny-x", proposal["approval_id"])
    assert unapproved.status_code == 403
    assert await org.rules() == ["deny-x"]


async def test_an_approval_is_bound_to_one_change_one_version_and_its_requester(org: Org) -> None:
    csrf = await org.as_owner()
    await _add(org.client, csrf, _add_body("deny-x", "DENY", "x"))
    await _add(org.client, csrf, _add_body("deny-y", "DENY", "y"))
    proposal = await _propose(org, {"operation": "remove", "rule_id": "deny-x"})
    assert (await _approve(org, proposal["approval_id"])).status_code == 200

    # A different change with the same approval.
    other_rule = await _execute_removal(org, "deny-y", proposal["approval_id"])
    assert other_rule.status_code == 403, other_rule.text

    # A different requester (the administrator) cannot use the owner's approval.
    stolen = await _execute_removal(
        org, "deny-x", proposal["approval_id"], secret=org.admin_secret, csrf=await org.as_admin()
    )
    assert stolen.status_code == 403, stolen.text

    # A policy change in between (tightening is allowed) moves the version: the approval no longer fits.
    assert (
        await _add(org.client, await org.as_owner(), _add_body("deny-z", "DENY", "z"))
    ).status_code == 200
    stale = await _execute_removal(org, "deny-x", proposal["approval_id"])
    assert stale.status_code == 403, stale.text
    assert await org.rules() == ["deny-x", "deny-y", "deny-z"]


async def test_a_forged_step_up_does_not_spend_the_approval_or_authorize_the_edit(org: Org) -> None:
    csrf = await org.as_owner()
    await _add(org.client, csrf, _add_body("deny-x", "DENY", "x"))
    proposal = await _propose(org, {"operation": "remove", "rule_id": "deny-x"})
    assert (await _approve(org, proposal["approval_id"])).status_code == 200

    csrf = await org.as_owner()

    async def call(headers):
        return await org.client.delete(
            "/api/v1/web/policy/rules/deny-x",
            headers={**headers, APPROVAL: proposal["approval_id"]},
        )

    for method, token in (
        ("mfa_totp", "123456"),
        ("oidc_auth_time", "valid-token-1234567890"),
        ("webauthn", "x" * 20),
    ):
        challenge = await call({"X-WP-CSRF": csrf})
        nonce = _get_step_up_detail(challenge)["required_nonce"]
        forged = await call(
            {
                "X-WP-CSRF": csrf,
                "X-Step-Up-Nonce": nonce,
                "X-Step-Up-Method": method,
                "X-Step-Up-Token": token,
            }
        )
        assert forged.status_code == 403, (method, forged.text)
        assert await org.rules() == ["deny-x"]
    # The approval survived the forged attempts and still works with a genuine code.
    done = await _execute_removal(org, "deny-x", proposal["approval_id"])
    assert done.status_code == 200, done.text


async def test_a_reorder_that_moves_an_allow_above_a_restriction_is_a_loosening(org: Org) -> None:
    csrf = await org.as_owner()
    # ALLOW first, then a restriction on a *different* action so appending is legal.
    assert (await _add(org.client, csrf, _add_body("deny-x", "DENY", "x"))).status_code == 200
    proposal = await _propose(org, {"operation": "add", "rule": _add_body("allow-y", "ALLOW", "y")})
    assert proposal["kind"] == "LOOSENING"
    # An already-restrictive-then-allow list reordered so ALLOW precedes DENY is refused without approval.
    csrf = await org.as_owner()
    await _approve(org, proposal["approval_id"])
    csrf = await org.as_owner()

    async def add_with_approval(headers):
        return await org.client.post(
            "/api/v1/web/policy/rules",
            headers={**headers, APPROVAL: proposal["approval_id"]},
            json=_add_body("allow-y", "ALLOW", "y"),
        )

    headers = await org.step_up_headers(csrf, org.owner_secret, add_with_approval)
    assert (await add_with_approval(headers)).status_code == 200
    assert await org.rules() == ["deny-x", "allow-y"]
    csrf = await org.as_owner()
    reorder = await org.client.post(
        "/api/v1/web/policy/reorder",
        headers={"X-WP-CSRF": csrf},
        json={"rule_ids": ["allow-y", "deny-x"]},
    )
    assert reorder.status_code == 403, reorder.text
    assert await org.rules() == ["deny-x", "allow-y"]


async def test_an_api_key_can_tighten_but_never_loosen_in_tiered_mode(
    org: Org, monkeypatch
) -> None:
    from responsibleai.db import OrgRepository
    from responsibleai.rbac.models import Role

    monkeypatch.setattr(app_module.settings, "auth_enabled", True)
    csrf = await org.as_owner()
    await _add(org.client, csrf, _add_body("deny-x", "DENY", "x"))
    _record, raw = await OrgRepository(_engine()).create_key(org.org_id, "ci", role=Role.ADMIN)
    key = {"Authorization": f"Bearer {raw}"}
    anonymous = AsyncClient(transport=org.client._transport, base_url="http://test")
    try:
        tighten = await anonymous.post(
            "/api/governance/policy/rules", headers=key, json=_add_body("deny-k", "DENY", "k")
        )
        assert tighten.status_code == 200, tighten.text
        loosen = await anonymous.delete("/api/governance/policy/rules/deny-x", headers=key)
        assert loosen.status_code == 403, loosen.text
        allow = await anonymous.post(
            "/api/governance/policy/rules", headers=key, json=_add_body("allow-k", "ALLOW", "k2")
        )
        assert allow.status_code == 403, allow.text
    finally:
        await anonymous.aclose()
    assert await org.rules() == ["deny-x", "deny-k"]
