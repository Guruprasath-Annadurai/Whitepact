# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Reject a release candidate that is missing a mandatory security control.

Commit ancestry is not sufficient: a cherry-pick changes the commit id.
This gate checks that the current tree still contains the controls and
that their regression tests are present. A green CI job that skips this
script is not a qualification of those controls.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Semantic markers. Each control names the files that must contain it
# and a regression test that must name the behavior.
CONTROLS: dict[str, dict[str, list[str]]] = {
    "P0-01-oidc-tenant-admission": {
        "files": [
            "src/responsibleai/auth/tenant_admission.py",
            "src/responsibleai/dashboard/app.py",
            "src/responsibleai/mcp/server.py",
        ],
        "markers": ["admit_sso_principal", "unknown_organization"],
        "tests": ["tests/test_p0_tenant_admission.py"],
        "test_markers": ["test_oidc_unknown_organization_is_rejected"],
    },
    "P0-02-saml-tenant-admission": {
        "files": [
            "src/responsibleai/dashboard/app.py",
            "src/responsibleai/auth/saml.py",
        ],
        "markers": ["SAML tenant admission failed", "validate_session_token"],
        "tests": ["tests/test_p0_tenant_admission.py", "tests/test_saml_app_routes.py"],
        "test_markers": [
            "test_saml_expired_session_is_rejected",
            "test_acs_unknown_tenant_does_not_mint_a_session",
        ],
    },
    "P0-03-vc-tenant-admission": {
        "files": ["src/responsibleai/mcp/server.py"],
        "markers": ["admit_sso_principal", 'authentication_method="vc"'],
        "tests": ["tests/test_mcp_verified_principal.py"],
        "test_markers": ["test_vc_unknown_org_leaves_no_principal_row"],
    },
    "P1-04-principal-poisoning": {
        "files": ["src/responsibleai/mcp/server.py"],
        "markers": ["must not poison the directory"],
        "tests": ["tests/test_mcp_verified_principal.py"],
        "test_markers": ["test_vc_unbound_existing_org_leaves_no_principal_row"],
    },
    "P1-05-runner-immutability": {
        "files": ["src/responsibleai/isolation/container_backend.py"],
        "markers": ["/opt/whitepact/runner.py", "is_reserved_runner_path"],
        "tests": ["tests/test_runner_immutability.py"],
        "test_markers": ["test_direct_backend_rejects_caller_runner"],
    },
    "PR-176-trust-fail-closed": {
        "files": [
            "src/responsibleai/integrations/a2a_adapter.py",
            "src/responsibleai/integrations/langchain_middleware.py",
        ],
        "markers": ["fails closed", "trust lookup unavailable"],
        "tests": ["tests/test_a2a_adapter.py"],
        "test_markers": ["trust lookup unavailable"],
    },
}


def _read(rel: str) -> str:
    path = ROOT / rel
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _function_names(paths: list[str]) -> set[str]:
    names: set[str] = set()
    for rel in paths:
        text = _read(rel)
        if not text:
            continue
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(node.name)
    return names


def evaluate() -> dict[str, object]:
    missing: list[dict[str, str]] = []
    present: list[str] = []
    for control, spec in CONTROLS.items():
        blob = "\n".join(_read(path) for path in spec["files"])
        tests = "\n".join(_read(path) for path in spec["tests"])
        functions = _function_names(spec["tests"])
        ok = True
        for marker in spec["markers"]:
            if marker not in blob:
                missing.append({"control": control, "missing": marker, "kind": "implementation"})
                ok = False
        for marker in spec["test_markers"]:
            if marker.startswith("test_"):
                if marker not in functions:
                    missing.append(
                        {
                            "control": control,
                            "missing": marker,
                            "kind": "regression-function",
                        }
                    )
                    ok = False
            elif marker not in tests:
                missing.append({"control": control, "missing": marker, "kind": "regression-text"})
                ok = False
        if ok:
            present.append(control)
    return {
        "gate": "security-fix-inclusion",
        "text_match_is_not_enforcement": True,
        "behavioral_gate": "scripts/check_security_regressions.py",
        "present": present,
        "missing": missing,
        "passed": not missing,
    }


def main() -> int:
    report = evaluate()
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
