# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Behavioral branches the Python 3.11 CI tracer can record.

GitHub Actions on 3.11 measured 5699/7124 pure branches. The same tests
passed on 3.12 at 5725/7124. Several of those extra 3.12 arcs sit in
async regions the 3.11 C tracer does not attribute. These tests execute
synchronous contracts that were still absent from both runs: an
unparseable identity-provider timestamp, MCP argument rejection, org
ceiling drops, and CLI failure rendering.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import timedelta

import pytest

os.environ.setdefault("RAI_AUTH_ENABLED", "false")
os.environ.setdefault("RAI_LOG_JSON", "false")
os.environ.setdefault("RAI_LOG_LEVEL", "WARNING")
os.environ.setdefault("RAI_ALLOW_ALL_ORIGINS", "true")
os.environ.setdefault("RAI_AUTO_MIGRATE", "false")

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard.app import app, settings
from responsibleai.enterprise.errors import PROVIDER_SIGNATURE_INVALID, EnterpriseError
from responsibleai.enterprise.preflight import DEV_IDENTITY_WEBHOOK_SECRET
from responsibleai.enterprise.verification import HmacVerificationProvider
from responsibleai.formula.authority.algebra import (
    atoms_from_tuples,
    authority_subset,
    conflict_resolution_denies_first,
    grant_contained_in_issuer_authority,
    grant_restriction,
    grant_union,
    validate_delegation,
)
from responsibleai.formula.authority.models import OrgAuthorityCeilingModel
from responsibleai.formula.authority.wildcard import WILDCARD
from responsibleai.formula.errors import CrossTenantReference
from responsibleai.mcp.argument_validation import validate_tool_arguments
from responsibleai.sovereign.cli_format import failure_line, render_human
from tests.formula.helpers import make_grant


def _sign_idv(payload: bytes, timestamp: str) -> str:
    return hmac.new(
        DEV_IDENTITY_WEBHOOK_SECRET.encode(),
        payload + timestamp.encode(),
        hashlib.sha256,
    ).hexdigest()


@pytest.fixture()
async def client():
    orig = (settings.database_url, settings.db_path, settings.auto_migrate)
    settings.database_url = None
    settings.db_path = ":memory:"
    settings.auto_migrate = False
    try:
        async with LifespanManager(app, startup_timeout=15) as manager:
            async with AsyncClient(
                transport=ASGITransport(app=manager.app), base_url="http://test"
            ) as ac:
                yield ac
    finally:
        settings.database_url, settings.db_path, settings.auto_migrate = orig


class TestIdentityTimestampReject:
    def test_provider_rejects_unparseable_timestamp(self) -> None:
        provider = HmacVerificationProvider("secret")
        payload = b'{"event_id":"e-bad-ts"}'
        timestamp = "not-a-timestamp"
        signature = hmac.new(b"secret", payload + timestamp.encode(), hashlib.sha256).hexdigest()
        with pytest.raises(EnterpriseError) as exc:
            provider.verify_webhook(payload=payload, signature=signature, timestamp=timestamp)
        assert exc.value.code == PROVIDER_SIGNATURE_INVALID
        assert "timestamp" in exc.value.message.lower()

    async def test_webhook_rejects_unparseable_timestamp(self, client: AsyncClient) -> None:
        payload = b'{"event_id":"e-http","subject_id":"user-1","outcome":"VERIFIED"}'
        timestamp = "not-a-timestamp"
        response = await client.post(
            "/api/enterprise/identity/verification/webhook",
            content=payload,
            headers={
                "X-Identity-Signature": _sign_idv(payload, timestamp),
                "X-Identity-Timestamp": timestamp,
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 403
        body = response.json()
        assert body["error"] == PROVIDER_SIGNATURE_INVALID
        assert "timestamp" in body["message"].lower()


class TestMcpArgumentRejection:
    def test_null_is_legal_only_when_schema_allows_it(self) -> None:
        ok, err = validate_tool_arguments(
            "scan",
            {"note": None},
            {"properties": {"note": {"type": "null"}}},
        )
        assert err is None and ok == {"note": None}

        _ok, err = validate_tool_arguments(
            "scan",
            {"note": None},
            {"properties": {"note": {}}},
        )
        assert err is None

        _ok, err = validate_tool_arguments(
            "scan",
            {"note": None},
            {"properties": {"note": {"type": "string"}}},
        )
        assert err is not None
        assert err["field"] == "note"
        assert "null" in err["message"].lower()

    def test_unknown_python_type_is_rejected(self) -> None:
        _ok, err = validate_tool_arguments(
            "scan",
            {"blob": object()},
            {"properties": {"blob": {"type": "string"}}},
        )
        assert err is not None
        assert err["tool"] == "scan"
        assert "object" in err["message"]

    def test_numeric_bounds_reject_out_of_range(self) -> None:
        schema = {"properties": {"n": {"type": "number", "minimum": 1, "maximum": 3}}}
        _ok, low = validate_tool_arguments("scan", {"n": 0}, schema)
        _ok, high = validate_tool_arguments("scan", {"n": 4}, schema)
        _ok, ok = validate_tool_arguments("scan", {"n": 2}, schema)
        assert low is not None and ">=" in low["message"]
        assert high is not None and "<=" in high["message"]
        assert ok is None

    def test_integer_satisfies_number_schema(self) -> None:
        ok, err = validate_tool_arguments(
            "scan",
            {"n": 2},
            {"properties": {"n": {"type": "number"}}},
        )
        assert err is None and ok == {"n": 2}

    def test_nested_additional_properties_are_rejected(self) -> None:
        schema = {
            "properties": {
                "meta": {
                    "type": "object",
                    "properties": {"ok": {"type": "string"}},
                    "additionalProperties": False,
                }
            }
        }
        _ok, err = validate_tool_arguments("scan", {"meta": {"nope": "x"}}, schema)
        assert err is not None
        assert "Unknown field" in err["message"]

        schema_typed = {
            "properties": {
                "meta": {
                    "type": "object",
                    "additionalProperties": {"type": "integer"},
                }
            }
        }
        _ok, err = validate_tool_arguments("scan", {"meta": {"n": "bad"}}, schema_typed)
        assert err is not None
        assert err["field"] == "meta.n"

        ok, err = validate_tool_arguments("scan", {"meta": {"n": 1}}, schema_typed)
        assert err is None and ok is not None

    def test_top_level_unknown_fields_are_rejected(self) -> None:
        schema = {
            "properties": {"q": {"type": "string"}},
            "additionalProperties": False,
        }
        _ok, err = validate_tool_arguments("scan", {"q": "ok", "extra": 1}, schema)
        assert err is not None
        assert err["field"] == "arguments"
        assert "extra" in err["message"]

        ok, err = validate_tool_arguments("scan", {"q": "ok"}, schema)
        assert err is None and ok == {"q": "ok"}

    def test_unknown_field_without_declared_properties(self) -> None:
        _ok, err = validate_tool_arguments(
            "scan",
            {"extra": 1},
            {"additionalProperties": False},
        )
        assert err is not None
        assert err["field"] == "extra"


class TestAuthorityCeilingAndSubset:
    def test_ceiling_drops_wildcard_and_disallowed_dimensions(self) -> None:
        wildcard_action = grant_union((make_grant("a", "s", actions=frozenset({WILDCARD})),))
        ceiling = OrgAuthorityCeilingModel(
            tenant_id="t1",
            org_id="o1",
            allowed_actions=frozenset({"read"}),
            allowed_resources=frozenset({"x"}),
        )
        assert grant_restriction(wildcard_action, ceiling) == frozenset()

        wildcard_resource = grant_union((make_grant("r", "s", resources=frozenset({WILDCARD})),))
        assert grant_restriction(wildcard_resource, ceiling) == frozenset()

        foreign = grant_union((make_grant("f", "s", resources=frozenset({"secret"})),))
        assert grant_restriction(foreign, ceiling) == frozenset()

        kept = grant_union((make_grant("k", "s"),))
        assert {t.action for t in grant_restriction(kept, ceiling)} == {"read"}

    def test_atoms_drop_grant_provenance(self) -> None:
        tuples = grant_union((make_grant("g", "s"),))
        atoms = atoms_from_tuples(tuples)
        assert {(a.action, a.resource, a.purpose) for a in atoms} == {
            (t.action, t.resource, t.purpose) for t in tuples
        }
        assert all(not hasattr(atom, "grant_id") for atom in atoms)

    def test_subset_rejects_widening(self) -> None:
        parent = make_grant("p", "s")
        assert authority_subset(make_grant("c", "s", tenant="other"), parent) is False
        assert (
            authority_subset(make_grant("c", "s", resources=frozenset({"other"})), parent) is False
        )
        assert authority_subset(make_grant("c", "s", allow_delegation=True), parent) is False
        earlier = parent.not_before - timedelta(hours=1)
        assert authority_subset(make_grant("c", "s", nb=earlier), parent) is False
        later = parent.expires_at + timedelta(days=1)
        assert authority_subset(make_grant("c", "s", exp=later), parent) is False

    def test_delegation_across_tenants_is_rejected(self) -> None:
        parent = make_grant("p", "org", allow_delegation=True)
        child = make_grant(
            "c",
            "agent",
            tenant="other",
            delegator="org",
            delegation_depth=1,
            allow_delegation=False,
        )
        with pytest.raises(CrossTenantReference, match="across tenants"):
            validate_delegation(parent, child)

    def test_issuer_authority_skips_non_matching_grants(self) -> None:
        child = make_grant("child", "agent", actions=frozenset({"read"}))
        at = child.not_before
        wrong_subject = make_grant("ig", "someone-else", actions=frozenset({"read"}))
        wrong_tenant = make_grant("ig2", "issuer", tenant="other", actions=frozenset({"read"}))
        expired = make_grant(
            "ig3",
            "issuer",
            actions=frozenset({"read"}),
            nb=at - timedelta(days=3),
            exp=at - timedelta(seconds=1),
        )
        assert (
            grant_contained_in_issuer_authority(
                child, (wrong_subject, wrong_tenant, expired), at, "issuer"
            )
            is False
        )

    def test_conflict_resolution_removes_denied_tuples(self) -> None:
        allowed = grant_union((make_grant("g", "s", actions=frozenset({"read", "write"})),))
        write_only = frozenset(t for t in allowed if t.action == "write")
        assert write_only
        assert conflict_resolution_denies_first(allowed, write_only) == frozenset(
            t for t in allowed if t.action != "write"
        )


class TestCliHumanRendering:
    def test_empty_and_non_dict_payloads(self) -> None:
        assert render_human(None) == "No result."
        assert render_human(12) == "12"
        assert failure_line("nope") is None
        assert failure_line({"disposition": "ALLOW"}) is None

    def test_summary_checks_items_and_graph(self) -> None:
        text = render_human(
            {
                "human_summary": "  blocked  ",
                "disposition": "",
                "status": "closed",
                "checks": ["plain", {"name": "scope", "result": "FAIL", "detail": "tenant"}],
                "items": ["raw", {"kind": "policy", "message": "missing purpose"}],
                "stages": [{"code": "intent", "summary": "recorded"}],
                "graph": {"nodes": [{"id": "a"}], "edges": "bad"},
                "envelope_hints": ["", "rotate the key"],
            }
        )
        assert text.startswith("blocked")
        assert "status: closed" in text
        assert "disposition:" not in text
        assert "- plain" in text or "plain" in text
        assert "[FAIL] scope — tenant" in text
        assert "policy: missing purpose" in text
        assert "trace stages: 1" in text
        assert "authority graph: 1 nodes, 0 edges" in text
        assert "hint: rotate the key" in text

    def test_cases_evidence_errors_and_fallback(self) -> None:
        long_hash = "a" * 64
        text = render_human(
            {
                "cases": [{"status": "FAIL"}, "skip"],
                "reconstruction": [
                    "not-a-record",
                    {
                        "evidence_id": "ev-1",
                        "decision": "DENY",
                        "identity_id": "id-1",
                        "integrity": {"hash": long_hash},
                    },
                ],
                "explanation": [{"summary": "purpose missing"}, "ignore"],
                "errors": ["sig mismatch"],
                "facts": [{"code": "DRIFT", "message": "pin moved"}],
                "steps": ["one"],
                "error": "rejected",
                "reason": "stale epoch",
            }
        )
        assert "cases: 2 (1 failed)" in text
        assert f"hash {long_hash[:12]}" in text
        assert "purpose missing" in text
        assert "errors:" in text and "sig mismatch" in text
        assert "drift facts: 1" in text
        assert "DRIFT: pin moved" in text
        assert "steps: 1" in text
        assert "error: rejected" in text
        assert "reason: stale epoch" in text

        fallback = render_human({"custom": ["a", "b"], "nested": {"k": 1}})
        assert "result:" in fallback
        assert "2 item(s)" in fallback
        assert "1 field(s)" in fallback

        huge = render_human({"note": "x" * 200})
        assert "..." in huge

    def test_failure_line_prefers_specific_diagnostics(self) -> None:
        assert failure_line({"error": "rejected", "reason": "stale epoch"}) == (
            "rejected: stale epoch"
        )
        assert failure_line({"error": "rejected"}) == "rejected"
        assert (
            failure_line({"checks": [{"name": "scope", "result": "FAIL", "detail": "tenant"}]})
            == "scope: tenant"
        )
        assert failure_line({"disposition": "rejected", "message": "no grant"}) == "no grant"
