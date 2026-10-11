# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""SDK/CLI product completion: human output, replay, prove, and WhitePactClient."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from click.testing import CliRunner

from responsibleai.governance.evidence import EvidenceRecord, compute_canonical_evidence_hash
from responsibleai.governance.evidence_bundle import build_evidence_bundle
from responsibleai.mcp.trust_domain import (
    ENTERPRISE_STDIO_REFUSAL,
    refuse_ungoverned_stdio_exit,
)
from responsibleai.sovereign import devconfig
from responsibleai.sovereign.capsule import create_capsule
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.exit_codes import (
    EXIT_GOVERNANCE,
    EXIT_INVALID,
    EXIT_OK,
    EXIT_UNAVAILABLE,
)
from responsibleai.sovereign.reachability import ProbeResult, probe_base_url
from whitepact.cli import main
from whitepact.client import (
    WhitePactAuthError,
    WhitePactClient,
    WhitePactConflictError,
    WhitePactDNSError,
    WhitePactForbiddenError,
    WhitePactMalformedResponseError,
    WhitePactNotFoundError,
    WhitePactProtocolError,
    WhitePactRateLimitError,
    WhitePactSchemaError,
    WhitePactServerError,
    WhitePactTenantError,
    WhitePactTimeoutError,
    WhitePactValidationError,
)

_API_HEADERS = {"X-API-Version": "1.3.1", "X-API-Min-Version": "1.0.0"}


def _record(**overrides: object) -> dict:
    fields: dict = {
        "evidence_id": "ev-1",
        "organization_id": "org-a",
        "action_id": "act-1",
        "agent_id": "agent-1",
        "identity_id": "principal-1",
        "action_type": "rai_health",
        "target": "rai_health",
        "argument_keys": [],
        "authority_delegated_by": "root-authority",
        "delegation_chain": ["root-authority", "principal-1"],
        "decision": "ALLOW",
        "reason_codes": ["policy_allow"],
        "evaluated_at": datetime(2026, 1, 2, tzinfo=UTC),
        "recorded_at": "2026-01-02T00:00:01+00:00",
        "prev_hash": "0" * 64,
        "integrity_version": 2,
        "integrity_status": "CANONICAL_CHAINED",
        "authentication_method": "api_key",
        "purpose": "developer-journey",
        "execution_authorization_id": "grant-1",
        "execution_target": "rai_health",
        "approval_id": None,
    }
    fields.update(overrides)
    record = EvidenceRecord(**fields)
    sealed = record.to_dict()
    sealed["hash"] = compute_canonical_evidence_hash(record.prev_hash, record)
    return sealed


def _write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _patch_context(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "responsibleai.sovereign.devconfig.CONFIG_DIR",
        tmp_path,
    )
    monkeypatch.setattr(
        "responsibleai.sovereign.devconfig.CONTEXT_FILE",
        tmp_path / "context.json",
    )


def test_probe_classifies_http_and_network_without_credentials() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("Authorization", ""))
        return httpx.Response(403)

    result = probe_base_url(
        "https://wp.example",
        transport=httpx.MockTransport(handler),
    )
    assert result.ok is False
    assert result.kind == "http_403"
    assert seen == [""]

    def down(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    failed = probe_base_url("https://wp.example", transport=httpx.MockTransport(down))
    assert failed.kind == "network"
    assert failed.ok is False


def test_human_doctor_xray_are_not_silent() -> None:
    runner = CliRunner()
    doctor = runner.invoke(main, ["doctor"])
    assert doctor.exit_code == EXIT_OK
    assert "protocol" in doctor.stdout
    assert "[PASS]" in doctor.stdout
    xray = runner.invoke(main, ["xray", "--org", "org-test"])
    assert xray.exit_code == EXIT_OK
    assert "authority graph" in xray.stdout
    assert xray.stdout.strip()


def test_json_doctor_is_deterministic() -> None:
    runner = CliRunner()
    first = runner.invoke(main, ["doctor", "--json"])
    second = runner.invoke(main, ["doctor", "--json"])
    assert first.exit_code == EXIT_OK
    assert first.stdout == second.stdout
    payload = json.loads(first.stdout)
    assert "checks" in payload
    assert first.stderr == ""


def test_explain_invalid_input_is_actionable() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["explain", "--org", "org-e"])
    assert result.exit_code == EXIT_INVALID
    assert "evidence_id or identity_id required" in result.stdout
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr


def test_trace_missing_evidence_fails_closed() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["trace", "--org", "org-e", "--evidence", "missing"])
    assert result.exit_code == EXIT_GOVERNANCE
    assert "fails closed" in result.stderr
    assert "Traceback" not in result.output


def test_doctor_remote_missing_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_context(monkeypatch, tmp_path)
    monkeypatch.delenv("WHITEPACT_API_KEY", raising=False)
    result = CliRunner().invoke(main, ["doctor", "--remote"])
    assert result.exit_code == EXIT_INVALID
    assert "whitepact connect" in result.stdout
    assert "WHITEPACT_API_KEY" in result.stdout


def test_doctor_remote_missing_auth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_context(monkeypatch, tmp_path)
    monkeypatch.delenv("WHITEPACT_API_KEY", raising=False)
    (tmp_path / "context.json").write_text(
        json.dumps(
            {
                "base_url": "http://127.0.0.1:9",
                "organization_id": "local-only",
                "environment": "development",
                "verification_state": "unverified",
                "verification_detail": "",
            }
        ),
        encoding="utf-8",
    )

    def _ok(_url: str, **_kwargs: object) -> ProbeResult:
        return ProbeResult(ok=True, kind="ok", message="VERIFIED CONNECTION")

    monkeypatch.setattr("responsibleai.sovereign.reachability.probe_base_url", _ok)
    result = CliRunner().invoke(main, ["doctor", "--remote", "--json"])
    assert result.exit_code == EXIT_INVALID
    payload = json.loads(result.stdout)
    auth = next(item for item in payload["checks"] if item["name"] == "auth")
    assert auth["result"] == "FAIL"
    assert "WHITEPACT_API_KEY" in auth["detail"]
    assert "local-only" not in result.stdout or "not authority" in result.stdout


@pytest.mark.parametrize(
    ("kind", "message", "expected"),
    [
        ("network", "Could not connect to wp.example.", EXIT_UNAVAILABLE),
        ("dns", "DNS lookup failed for wp.example.", EXIT_UNAVAILABLE),
        ("timeout", "Timed out after 5s contacting wp.example.", EXIT_UNAVAILABLE),
        ("http_403", "HTTP 403 from /api/health.", EXIT_GOVERNANCE),
        ("http_404", "HTTP 404 from /api/health.", EXIT_UNAVAILABLE),
        ("http_429", "HTTP 429 from /api/health.", EXIT_UNAVAILABLE),
        ("http_5xx", "HTTP 503 from /api/health.", EXIT_UNAVAILABLE),
    ],
)
def test_doctor_remote_transport_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    kind: str,
    message: str,
    expected: int,
) -> None:
    _patch_context(monkeypatch, tmp_path)
    monkeypatch.setenv("WHITEPACT_API_KEY", "present-but-not-printed")
    (tmp_path / "context.json").write_text(
        json.dumps(
            {
                "base_url": "https://wp.example",
                "organization_id": None,
                "environment": "development",
                "verification_state": "unverified",
                "verification_detail": "",
            }
        ),
        encoding="utf-8",
    )

    def _probe(_url: str, **_kwargs: object) -> ProbeResult:
        return ProbeResult(ok=False, kind=kind, message=message, status_code=503)

    monkeypatch.setattr("responsibleai.sovereign.reachability.probe_base_url", _probe)
    result = CliRunner().invoke(main, ["doctor", "--remote"])
    assert result.exit_code == expected
    assert message in result.stdout
    assert "present-but-not-printed" not in result.output
    assert "Traceback" not in result.output


def test_connect_distinguishes_verified_and_unverified(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_context(monkeypatch, tmp_path)
    calls = {"n": 0}

    def _probe(url: str, **_kwargs: object) -> ProbeResult:
        calls["n"] += 1
        if calls["n"] == 1:
            return ProbeResult(ok=False, kind="network", message="Could not connect to 127.0.0.1.")
        return ProbeResult(
            ok=True,
            kind="ok",
            message="VERIFIED CONNECTION — /api/health returned HTTP 200. This is not authorization.",
        )

    monkeypatch.setattr("responsibleai.sovereign.reachability.probe_base_url", _probe)
    unverified = CliRunner().invoke(
        main, ["connect", "--url", "http://127.0.0.1:9", "--org", "hint"]
    )
    assert unverified.exit_code == EXIT_OK
    assert "SAVED UNVERIFIED CONTEXT" in unverified.stdout
    assert "No credentials were stored" in unverified.stdout
    saved = devconfig.load_connection()
    assert saved.verification_state == "unverified"
    blob = (tmp_path / "context.json").read_text(encoding="utf-8")
    assert "api_key" not in blob
    assert "token" not in blob
    verified = CliRunner().invoke(main, ["connect", "--url", "http://127.0.0.1:8000"])
    saved_after = (tmp_path / "context.json").read_text(encoding="utf-8")
    loaded = devconfig.load_connection()
    assert verified.exit_code == EXIT_OK, verified.output
    assert "VERIFIED CONNECTION" in verified.stdout
    assert "SAVED UNVERIFIED CONTEXT" not in verified.stdout
    assert '"verification_state": "verified"' in saved_after, saved_after
    assert loaded.verification_state == "verified"


def test_connect_rejects_embedded_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_context(monkeypatch, tmp_path)
    result = CliRunner().invoke(
        main, ["connect", "--url", "http://user:super-secret@127.0.0.1:8000"]
    )
    assert result.exit_code == EXIT_INVALID
    assert "super-secret" not in result.output
    assert not (tmp_path / "context.json").exists()


def test_replay_and_prove_round_trip(tmp_path: Path) -> None:
    path = _write(tmp_path, _record())
    runner = CliRunner()
    replay = runner.invoke(main, ["replay", "--file", str(path), "--org", "org-a", "--json"])
    assert replay.exit_code == EXIT_OK, replay.output
    body = json.loads(replay.stdout)
    assert body["disposition"] == "REPRODUCED"
    assert body["executed"] is False
    assert body["zero_effect"] is True
    assert body["reconstruction"][0]["identity_id"] == "principal-1"
    assert body["reconstruction"][0]["decision"] == "ALLOW"
    assert body["reconstruction"][0]["integrity"]["hash"]
    human = runner.invoke(main, ["replay", "--file", str(path), "--org", "org-a"])
    assert human.exit_code == EXIT_OK
    assert "REPRODUCED" in human.stdout
    assert "principal-1" in human.stdout
    output = tmp_path / "proof.json"
    prove = runner.invoke(
        main,
        ["prove", "--file", str(path), "--org", "org-a", "--output", str(output), "--json"],
    )
    assert prove.exit_code == EXIT_OK, prove.output
    artifact = json.loads(prove.stdout)
    assert artifact["disposition"] == "PROVED"
    assert artifact["artifact_type"] == "whitepact.verification"
    subject = artifact["subjects"][0]
    assert subject["organization_id"] == "org-a"
    assert subject["identity_id"] == "principal-1"
    assert subject["decision"] == "ALLOW"
    assert subject["authority"]["authority_delegated_by"] == "root-authority"
    assert subject["integrity"]["hash"]
    assert artifact["verifier"]["protocol_version"]
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["subjects"] == artifact["subjects"]


def test_replay_cross_tenant_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path, _record(organization_id="org-b", evidence_id="ev-b"))
    result = CliRunner().invoke(main, ["replay", "--file", str(path), "--org", "org-a", "--json"])
    assert result.exit_code == EXIT_GOVERNANCE
    assert "REPRODUCED" not in result.stdout
    assert "different tenant" in result.stderr
    prove = CliRunner().invoke(main, ["prove", "--file", str(path), "--org", "org-a", "--json"])
    assert prove.exit_code == EXIT_GOVERNANCE
    assert "PROVED" not in prove.stdout


def test_replay_tampered_and_missing_rejected(tmp_path: Path) -> None:
    tampered = _record()
    tampered["decision"] = "DENY"
    path = _write(tmp_path, tampered)
    result = CliRunner().invoke(main, ["replay", "--file", str(path), "--json"])
    assert result.exit_code == EXIT_GOVERNANCE
    assert "Tampered" in result.stderr
    missing = CliRunner().invoke(main, ["replay", "--file", str(tmp_path / "nope.json"), "--json"])
    assert missing.exit_code == EXIT_INVALID
    assert "not found" in missing.stderr
    malformed = tmp_path / "bad.json"
    malformed.write_text("{", encoding="utf-8")
    bad = CliRunner().invoke(main, ["prove", "--file", str(malformed), "--json"])
    assert bad.exit_code == EXIT_INVALID
    assert "JSON" in bad.stderr


def test_replay_capsule_without_evidence_fails_closed(tmp_path: Path) -> None:
    capsule = create_capsule(SovereignContext(organization_id="org-a"))
    path = _write(tmp_path, capsule.model_dump())
    result = CliRunner().invoke(main, ["replay", "--file", str(path), "--org", "org-a", "--json"])
    assert result.exit_code == EXIT_INVALID
    assert "no governance evidence" in result.stderr


def test_replay_embedded_capsule_evidence(tmp_path: Path) -> None:
    record = _record()
    capsule = create_capsule(
        SovereignContext(organization_id="org-a"),
        timeline=[record],
    )
    path = _write(tmp_path, capsule.model_dump())
    result = CliRunner().invoke(main, ["replay", "--file", str(path), "--org", "org-a", "--json"])
    assert result.exit_code == EXIT_OK, result.output
    body = json.loads(result.stdout)
    assert body["executed"] is False
    assert body["reconstruction"][0]["evidence_id"] == "ev-1"


def test_replay_bundle_and_forged_header(tmp_path: Path) -> None:
    sealed = _record()
    record = EvidenceRecord(
        **{
            **{
                k: sealed[k]
                for k in (
                    "evidence_id",
                    "organization_id",
                    "action_id",
                    "agent_id",
                    "identity_id",
                    "action_type",
                    "target",
                    "authority_delegated_by",
                    "decision",
                )
            },
            "argument_keys": [],
            "evaluated_at": datetime(2026, 1, 2, tzinfo=UTC),
            "recorded_at": sealed["recorded_at"],
            "prev_hash": sealed["prev_hash"],
            "hash": sealed["hash"],
            "integrity_version": 2,
            "delegation_chain": sealed["delegation_chain"],
            "reason_codes": sealed["reason_codes"],
            "execution_authorization_id": sealed["execution_authorization_id"],
            "execution_target": sealed["execution_target"],
            "authentication_method": sealed["authentication_method"],
            "purpose": sealed["purpose"],
            "integrity_status": sealed["integrity_status"],
        }
    )
    bundle = build_evidence_bundle([record], org_id="org-a").to_dict()
    path = _write(tmp_path, bundle)
    ok = CliRunner().invoke(main, ["prove", "--file", str(path), "--org", "org-a", "--json"])
    assert ok.exit_code == EXIT_OK, ok.output
    forged = dict(bundle)
    forged["org_id"] = "org-b"
    forged_path = tmp_path / "forged.json"
    forged_path.write_text(json.dumps(forged), encoding="utf-8")
    rejected = CliRunner().invoke(main, ["replay", "--file", str(forged_path), "--org", "org-b"])
    assert rejected.exit_code == EXIT_GOVERNANCE
    assert "Forged" in rejected.stderr or "forged" in rejected.stderr.lower()


def _client(handler) -> WhitePactClient:
    return WhitePactClient(
        "https://wp.example",
        api_key="super-secret-token",
        timeout=2.0,
        max_retries=2,
        retry_backoff=0,
        transport=httpx.MockTransport(handler),
    )


def test_client_rejects_missing_auth_and_credential_url() -> None:
    with pytest.raises(WhitePactAuthError):
        WhitePactClient("https://wp.example", api_key="")
    with pytest.raises(ValueError, match="credentials"):
        WhitePactClient("https://user:leak-me@wp.example", api_key="token")


def test_client_hosted_journey() -> None:
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        assert request.headers["Authorization"] == "Bearer super-secret-token"
        assert "org_id" not in str(request.url)
        if request.url.path.endswith("/governance/policy"):
            return httpx.Response(
                200, json={"org_id": "org-server", "rules": []}, headers=_API_HEADERS
            )
        if request.url.path.endswith("/governance/tools/call"):
            body = json.loads(request.content)
            assert body["purpose"] == "developer-first-success"
            assert "organization_id" not in body
            return httpx.Response(
                200,
                json={"tool": body["name"], "result": {"ok": True}, "outcome_status": "SUCCEEDED"},
                headers=_API_HEADERS,
            )
        if request.url.path.endswith("/governance/evidence"):
            return httpx.Response(
                200,
                json={
                    "evidence": [
                        {
                            "evidence_id": "ev-1",
                            "organization_id": "org-server",
                            "decision": "ALLOW",
                            "execution_authorization_id": "grant-1",
                        }
                    ],
                    "limit": 50,
                },
                headers=_API_HEADERS,
            )
        if request.url.path.endswith("/attestation"):
            return httpx.Response(
                200,
                json={
                    "evidence_id": "ev-1",
                    "organization_id": "org-server",
                    "decision": "ALLOW",
                    "evidence_hash": "abc",
                },
                headers=_API_HEADERS,
            )
        if request.url.path.endswith("/audit-log"):
            return httpx.Response(200, json={"entries": [], "total": 0}, headers=_API_HEADERS)
        if request.url.path.endswith("/revoke"):
            return httpx.Response(
                200,
                json={"identity_id": "principal-1", "revoked_delegation_ids": ["del-1"]},
                headers=_API_HEADERS,
            )
        raise AssertionError(request.url.path)

    with _client(handler) as client:
        authority = client.authenticate()
        assert authority.organization_id == "org-server"
        decision = client.protect(
            "rai_health",
            {},
            purpose="developer-first-success",
            expected_organization_id="org-server",
        )
        assert decision.decision == "ALLOW"
        assert decision.executed is True
        grant = client.inspect_execution_grant("ev-1")
        assert grant["grant_present"] is True
        assert grant["execution_authorization_id"] == "grant-1"
        assert grant["executed_by_client"] is False
        audit = client.query_audit()
        assert audit["total"] == 0
        revoked = client.revoke_delegation("principal-1", reason="end of session")
        assert revoked["revoked_delegation_ids"] == ["del-1"]
    assert ("POST", "/api/v1/governance/tools/call") in calls
    assert not hasattr(WhitePactClient, "execute")


def test_client_does_not_trust_caller_org() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            raise AssertionError("unsafe call must not be sent for a foreign org")
        return httpx.Response(200, json={"org_id": "org-server", "rules": []}, headers=_API_HEADERS)

    with _client(handler) as client:
        client.authenticate()
        with pytest.raises(WhitePactTenantError):
            client.protect("rai_health", {}, purpose="x", expected_organization_id="org-other")


def test_client_approval_then_server_execute() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/policy"):
            return httpx.Response(
                200, json={"org_id": "org-server", "rules": []}, headers=_API_HEADERS
            )
        if request.url.path.endswith("/tools/call"):
            return httpx.Response(
                200,
                json={
                    "error": "governance_approval_required",
                    "approval_id": "apr-1",
                    "action_id": "act-1",
                    "message": "approval required",
                },
                headers=_API_HEADERS,
            )
        if request.url.path.endswith("/resolve"):
            return httpx.Response(
                200, json={"approval_id": "apr-1", "status": "APPROVED"}, headers=_API_HEADERS
            )
        if request.url.path.endswith("/execute"):
            return httpx.Response(
                200, json={"approval_id": "apr-1", "result": {"ok": True}}, headers=_API_HEADERS
            )
        raise AssertionError(request.url.path)

    with _client(handler) as client:
        decision = client.protect("rai_health", {}, purpose="needs-human")
        assert decision.executed is False
        assert decision.decision == "REQUIRE_APPROVAL"
        assert decision.approval_id == "apr-1"
        client.resolve_approval("apr-1", "APPROVED")
        executed = client.execute_approval("apr-1")
        assert executed["result"]["ok"] is True


def test_client_does_not_retry_unsafe_mutation() -> None:
    posts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/policy"):
            return httpx.Response(
                200, json={"org_id": "org-server", "rules": []}, headers=_API_HEADERS
            )
        posts["n"] += 1
        return httpx.Response(503, json={"error": "unavailable"}, headers=_API_HEADERS)

    with _client(handler) as client:
        with pytest.raises(WhitePactServerError):
            client.protect("rai_health", {}, purpose="do-not-retry")
    assert posts["n"] == 1


def test_client_retries_safe_read_then_succeeds() -> None:
    gets = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        gets["n"] += 1
        if gets["n"] == 1:
            return httpx.Response(503, json={"error": "unavailable"}, headers=_API_HEADERS)
        return httpx.Response(200, json={"org_id": "org-server", "rules": []}, headers=_API_HEADERS)

    with _client(handler) as client:
        assert client.authenticate().organization_id == "org-server"
    assert gets["n"] == 2


@pytest.mark.parametrize(
    ("status", "exc_type"),
    [
        (401, WhitePactAuthError),
        (403, WhitePactForbiddenError),
        (409, WhitePactConflictError),
        (404, WhitePactNotFoundError),
        (422, WhitePactValidationError),
        (429, WhitePactRateLimitError),
        (500, WhitePactServerError),
        (502, WhitePactServerError),
    ],
)
def test_client_http_errors(status: int, exc_type: type[Exception]) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            json={"message": "detail super-secret-token"},
            headers=_API_HEADERS,
        )

    with _client(handler) as client:
        with pytest.raises(exc_type) as caught:
            client.authenticate()
    assert "super-secret-token" not in str(caught.value)


def test_client_timeout_dns_malformed_schema_protocol() -> None:
    def timeout(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    with _client(timeout) as client:
        with pytest.raises(WhitePactTimeoutError) as caught:
            client.authenticate()
    assert "super-secret-token" not in str(caught.value)

    def dns(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Name or service not known")

    with _client(dns) as client:
        with pytest.raises(WhitePactDNSError):
            client.authenticate()

    def malformed(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json", headers=_API_HEADERS)

    with _client(malformed) as client:
        with pytest.raises(WhitePactMalformedResponseError):
            client.authenticate()

    def schema(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"rules": []}, headers=_API_HEADERS)

    with _client(schema) as client:
        with pytest.raises(WhitePactSchemaError):
            client.authenticate()

    def protocol(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"org_id": "org-server", "rules": []},
            headers={"X-API-Version": "2.0.0", "X-API-Min-Version": "2.0.0"},
        )

    with _client(protocol) as client:
        with pytest.raises(WhitePactProtocolError):
            client.authenticate()


def test_client_timeout_on_protect_is_not_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/policy"):
            return httpx.Response(
                200, json={"org_id": "org-server", "rules": []}, headers=_API_HEADERS
            )
        calls["n"] += 1
        raise httpx.TimeoutException("timed out")

    with _client(handler) as client:
        with pytest.raises(WhitePactTimeoutError) as caught:
            client.protect("rai_health", {}, purpose="once")
    assert calls["n"] == 1
    assert "not retried" in str(caught.value)


def test_client_missing_grant_is_not_invented() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/policy"):
            return httpx.Response(
                200, json={"org_id": "org-server", "rules": []}, headers=_API_HEADERS
            )
        if request.url.path.endswith("/attestation"):
            return httpx.Response(
                200,
                json={
                    "evidence_id": "ev-1",
                    "organization_id": "org-server",
                    "decision": "REQUIRE_APPROVAL",
                },
                headers=_API_HEADERS,
            )
        return httpx.Response(
            200,
            json={
                "evidence": [
                    {
                        "evidence_id": "ev-1",
                        "organization_id": "org-server",
                        "decision": "REQUIRE_APPROVAL",
                        "execution_authorization_id": None,
                    }
                ],
                "limit": 50,
            },
            headers=_API_HEADERS,
        )

    with _client(handler) as client:
        grant = client.inspect_execution_grant("ev-1")
    assert grant["grant_present"] is False
    assert grant["execution_authorization_id"] is None
    assert grant["executed_by_client"] is False


def test_governed_http_route_stays_on_apply_governance() -> None:
    text = Path("src/responsibleai/dashboard/app.py").read_text(encoding="utf-8")
    start = text.index("async def governance_call_tool")
    chunk = text[start : start + 1800]
    assert "apply_governance" in chunk
    assert "dispatch_tool(" not in chunk


def test_enterprise_stdio_guard_still_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    from responsibleai.dashboard.config import get_settings

    monkeypatch.setattr(get_settings(), "mcp_trust_domain", "enterprise")
    with pytest.raises(SystemExit) as caught:
        refuse_ungoverned_stdio_exit()
    assert caught.value.code == 2
    assert "forbids ungoverned stdio" in ENTERPRISE_STDIO_REFUSAL


def test_community_stdio_guard_still_allows(monkeypatch: pytest.MonkeyPatch) -> None:
    from responsibleai.dashboard.config import get_settings

    monkeypatch.setattr(get_settings(), "mcp_trust_domain", "community")
    refuse_ungoverned_stdio_exit()


def test_replay_module_does_not_execute() -> None:
    text = Path("src/responsibleai/sovereign/evidence_replay.py").read_text(encoding="utf-8")
    assert "InternalToolExecutor" not in text
    assert "dispatch_tool" not in text
    assert "authorize_execution" not in text


def test_whitepact_bias_help_is_not_legacy_product_banner() -> None:
    result = CliRunner().invoke(main, ["bias", "--help"])
    assert result.exit_code == EXIT_OK
    assert "WhitePact" in result.stdout
    assert "open-source bias testing" not in result.stdout


def test_info_keeps_distribution_name_without_renaming() -> None:
    result = CliRunner().invoke(main, ["info"])
    assert result.exit_code == EXIT_OK
    assert "rai-governance-platform" in result.stdout
    assert "distribution lane" in result.stdout
    assert "product: WhitePact" in result.stdout
