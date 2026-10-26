# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Consequential SDK envelopes cannot promote nested non-success to completion."""

import runpy
from pathlib import Path

import httpx
import pytest
from sdk.python.rai_client.governance import GovernanceRuntimeClient, GovernanceToolOutcome


@pytest.mark.parametrize("decision", ["ALLOW", "ALLOW_WITH_REDACTION"])
def test_successful_canonical_decision_requires_execution_result(decision):
    assert GovernanceToolOutcome(
        {"decision": decision, "result": {}, "outcome_status": "SUCCEEDED"}
    ).completed
    assert not GovernanceToolOutcome({"decision": decision}).completed


@pytest.mark.parametrize(
    "payload",
    [
        {"result": {}, "outcome_status": "UNKNOWN"},
        {"result": {}, "decision": "DENY"},
        {"result": {}, "decision": "REQUIRE_APPROVAL"},
        {"result": {}, "decision": "QUARANTINE"},
        {"error": None},
        {"result": {"isError": True}},
    ],
)
def test_nested_approval_envelope_never_completes_non_success(payload):
    assert not GovernanceToolOutcome({"approval_id": "local-test", "result": payload}).completed


def test_nested_unknown_requires_reconciliation():
    assert GovernanceToolOutcome(
        {"approval_id": "local-test", "result": {"error": "governance_unknown_outcome"}}
    ).reconciliation_required


@pytest.mark.parametrize(
    "decision,property_name",
    [
        ("REQUIRE_APPROVAL", "requires_approval"),
        ("DENY", "denied"),
        ("QUARANTINE", "quarantined"),
    ],
)
def test_canonical_non_allowing_decisions_preserved(decision, property_name):
    outcome = GovernanceToolOutcome({"decision": decision})
    assert getattr(outcome, property_name)
    assert not outcome.completed


def test_deep_or_cyclic_response_fails_closed():
    raw = {}
    raw["result"] = raw
    outcome = GovernanceToolOutcome(raw)
    assert not outcome.completed
    assert outcome.reconciliation_required


async def test_policy_reads_existing_server_contract_without_tenant_input():
    seen = []

    def respond(request):
        seen.append(request)
        return httpx.Response(200, json={"rules": []})

    client = GovernanceRuntimeClient(
        "local-key", "http://127.0.0.1:8765", transport=httpx.MockTransport(respond)
    )
    assert await client.get_policy() == {"rules": []}
    assert len(seen) == 1
    assert seen[0].method == "GET"
    assert seen[0].url.path == "/api/governance/policy"
    assert seen[0].url.query == b""
    assert seen[0].headers["Authorization"] == "Bearer local-key"


async def test_executable_readiness_example_reads_only_and_does_not_print_key(monkeypatch, capsys):
    seen = []

    def respond(request):
        seen.append(request)
        payload = {
            "/api/governance/policy": {"rules": []},
            "/api/governance/approvals": {"pending": []},
            "/api/governance/evidence": {"evidence": []},
        }[request.url.path]
        return httpx.Response(200, json=payload)

    # The example intentionally imports the installed-package namespace. Source
    # unit CI has not installed the wheel; use the real SDK source, not a mock
    # module or an accidental SDK left in the developer's environment.
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "sdk/python"))
    example = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "sdk/python/examples/governance_readiness.py")
    )
    main = example["main"]
    main.__globals__["GovernanceRuntimeClient"] = lambda *args, **kwargs: GovernanceRuntimeClient(
        *args, **kwargs, transport=httpx.MockTransport(respond)
    )
    monkeypatch.setenv("WHITEPACT_API_KEY", "local-example-key")
    monkeypatch.setenv("WHITEPACT_URL", "http://127.0.0.1:8765")
    await main()
    assert len(seen) == 3
    assert all(request.method == "GET" for request in seen)
    output = capsys.readouterr().out
    assert '"authority_granted_by_client": false' in output
    assert "local-example-key" not in output
