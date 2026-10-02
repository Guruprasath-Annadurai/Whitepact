# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Cross-language governance SDK route contract (P1-03)."""

from __future__ import annotations

import inspect
from pathlib import Path

from sdk.python.rai_client.governance import GovernanceRuntimeClient
from tests.fixtures.governance_sdk_contract import GOVERNANCE_SDK_CONTRACT

TS_GOVERNANCE = Path(__file__).resolve().parents[1] / "sdk/typescript/src/governance.ts"


def _python_path_for(op: str, contract: dict) -> str:
    client = GovernanceRuntimeClient("k", base_url="http://example.test")
    if op == "tool_call":
        return client._url(contract["path"].lstrip("/"))
    if op == "list_approvals":
        return client._url(contract["path"].lstrip("/"))
    if op == "resolve_approval":
        return client._url(contract["path_template"].format(approval_id="apr-1").lstrip("/"))
    if op == "execute_approval":
        return client._url(contract["path_template"].format(approval_id="apr-1").lstrip("/"))
    if op == "revoke_delegation":
        return client._url(contract["path_template"].format(identity_id="agent-1").lstrip("/"))
    if op == "get_evidence":
        return client._url(contract["path_template"].format(evidence_id="ev-1").lstrip("/"))
    raise AssertionError(f"unknown op {op}")


def test_governance_contract_fixture_matches_python_urls() -> None:
    contract = GOVERNANCE_SDK_CONTRACT
    for op, spec in contract.items():
        url = _python_path_for(op, spec)
        assert url.startswith("http://example.test/api/")
        if "path_template" in spec:
            assert "{" not in url
        else:
            assert spec["path"].lstrip("/") in url


def test_governance_contract_methods_exist_on_python_client() -> None:
    methods = {
        "tool_call": "call_tool",
        "list_approvals": "list_approvals",
        "resolve_approval": "resolve_approval",
        "execute_approval": "execute_approval",
        "revoke_delegation": "revoke_delegation",
        "get_evidence": "get_evidence",
    }
    contract = GOVERNANCE_SDK_CONTRACT
    for op in contract:
        name = methods[op]
        assert hasattr(GovernanceRuntimeClient, name)
        assert inspect.iscoroutinefunction(getattr(GovernanceRuntimeClient, name))


def test_typescript_governance_module_declares_contract_paths() -> None:
    text = TS_GOVERNANCE.read_text(encoding="utf-8")
    contract = GOVERNANCE_SDK_CONTRACT
    for op, spec in contract.items():
        if "path_template" in spec:
            fragment = spec["path_template"].split("{", 1)[0].rstrip("/")
            fragment = fragment.removeprefix("/api/").lstrip("/")
            assert fragment in text, f"missing TS path fragment for {op}: {fragment}"
        else:
            assert spec["path"] in text or spec["path"].replace("/api/", "") in text, op
