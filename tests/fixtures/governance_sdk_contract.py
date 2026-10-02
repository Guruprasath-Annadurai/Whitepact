# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Shared governance SDK HTTP route contract (Python + TypeScript)."""

GOVERNANCE_SDK_CONTRACT: dict[str, dict[str, str]] = {
    "tool_call": {"method": "POST", "path": "/api/v1/governance/tools/call"},
    "list_approvals": {"method": "GET", "path": "/api/governance/approvals"},
    "resolve_approval": {
        "method": "POST",
        "path_template": "/api/governance/approvals/{approval_id}/resolve",
    },
    "execute_approval": {
        "method": "POST",
        "path_template": "/api/governance/approvals/{approval_id}/execute",
    },
    "revoke_delegation": {
        "method": "POST",
        "path_template": "/api/governance/delegations/{identity_id}/revoke",
    },
    "get_evidence": {
        "method": "GET",
        "path_template": "/api/governance/evidence/{evidence_id}",
    },
}
