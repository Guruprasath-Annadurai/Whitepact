# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Reject a release candidate that is missing a mandatory security control.

Commit ancestry is not sufficient: a cherry-pick changes the commit id.
This gate checks that the current tree still contains the controls and
that their regression tests are present. A green CI job that skips this
script is not a qualification of those controls.

Presence alone is cheap to fake, so a control only counts when:

* its implementation marker appears in code or a string, not only in a comment;
* each named regression function has a real body (an assert, ``pytest.raises``,
  ``pytest.fail`` or an explicit raise) and is not decorated skip/skipif/xfail;
* each named regression function is executed by the behavioural gate
  (``scripts/check_security_regressions.py``), which treats a skip as a failure.
"""

from __future__ import annotations

import ast
import importlib.util
import io
import json
import sys
import tokenize
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
        # Code, not the explanatory comment: the denial branch that returns before any
        # principal row is recorded.
        "markers": ["except TenantAdmissionDeniedError", "_principal_repo.record(claim)"],
        "tests": ["tests/test_mcp_verified_principal.py"],
        "test_markers": ["test_vc_unbound_existing_org_leaves_no_principal_row"],
    },
    "P1-05-runner-immutability": {
        "files": ["src/responsibleai/isolation/container_backend.py"],
        "markers": ["/opt/whitepact/runner.py", "is_reserved_runner_path"],
        "tests": ["tests/test_runner_immutability.py"],
        "test_markers": ["test_direct_backend_rejects_caller_runner"],
    },
    "P1-06-isolation-default-closed": {
        "files": [
            "src/responsibleai/isolation/mode.py",
            "src/responsibleai/isolation/broker.py",
            "src/responsibleai/governance/execution.py",
        ],
        "markers": ["unisolated_execution_allowed", "WHITEPACT_ALLOW_UNISOLATED_EXECUTION"],
        "tests": ["tests/test_isolation_fail_closed_default.py"],
        "test_markers": ["test_unset_environment_never_runs_the_tool_in_process"],
    },
    "P1-07-no-fabricated-deepfake-verdict": {
        "files": ["src/privacylabel/deepfake/detector.py"],
        "markers": ["DetectorNotValidatedError", "UnreadableMediaError", "VALIDATED_DETECTORS"],
        "tests": ["tests/test_deepfake_detector.py"],
        "test_markers": ["test_score_depends_on_the_input"],
    },
    "P1-08-eu-risk-tier-not-downgraded": {
        "files": ["src/responsibleai/compliance/engine.py"],
        "markers": ["_normalise_use_case"],
        "tests": ["tests/test_compliance_engine.py"],
        "test_markers": ["test_prohibited_use_is_never_downgraded_to_high"],
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


def _read(rel: str, root: Path = ROOT) -> str:
    path = root / rel
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _without_comments(source: str) -> str:
    """Source with comment tokens removed, so a marker cannot survive in a comment."""
    try:
        kept = [
            tok
            for tok in tokenize.generate_tokens(io.StringIO(source).readline)
            if tok.type != tokenize.COMMENT
        ]
    except (tokenize.TokenError, IndentationError):
        return source
    return tokenize.untokenize(kept)


def _is_skip_decorator(node: ast.expr) -> bool:
    target = node.func if isinstance(node, ast.Call) else node
    return isinstance(target, ast.Attribute) and target.attr in {"skip", "skipif", "xfail"}


def _has_assertion(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for node in ast.walk(func):
        if isinstance(node, (ast.Assert, ast.Raise)):
            return True
        if isinstance(node, ast.Call):
            callee = node.func
            name = callee.attr if isinstance(callee, ast.Attribute) else getattr(callee, "id", "")
            if name in {"raises", "fail", "assert_called", "assert_not_called"}:
                return True
    return False


def _test_functions(paths: list[str], root: Path) -> dict[str, list[str]]:
    """Map function name -> list of problems ('' list means the test is real)."""
    found: dict[str, list[str]] = {}
    for rel in paths:
        text = _read(rel, root)
        if not text:
            continue
        for node in ast.walk(ast.parse(text)):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            problems: list[str] = []
            if any(_is_skip_decorator(d) for d in node.decorator_list):
                problems.append("decorated skip/skipif/xfail")
            if not _has_assertion(node):
                problems.append("no assertion, raises or fail")
            found.setdefault(node.name, []).extend(problems)
    return found


def _behavioural_nodes() -> set[str]:
    """Function names that scripts/check_security_regressions.py actually executes."""
    path = Path(__file__).with_name("check_security_regressions.py")
    spec = importlib.util.spec_from_file_location("_wp_security_regressions", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {node.rsplit("::", 1)[-1] for node in module.NODES}


def evaluate(
    root: Path = ROOT,
    controls: dict[str, dict[str, list[str]]] | None = None,
    behavioural: set[str] | None = None,
) -> dict[str, object]:
    controls = CONTROLS if controls is None else controls
    executed = _behavioural_nodes() if behavioural is None else behavioural
    missing: list[dict[str, str]] = []
    present: list[str] = []
    for control, spec in controls.items():
        blob = "\n".join(_without_comments(_read(path, root)) for path in spec["files"])
        tests = "\n".join(_read(path, root) for path in spec["tests"])
        functions = _test_functions(spec["tests"], root)
        ok = True
        for marker in spec["markers"]:
            if marker not in blob:
                missing.append({"control": control, "missing": marker, "kind": "implementation"})
                ok = False
        for marker in spec["test_markers"]:
            if marker.startswith("test_"):
                if marker not in functions:
                    kind, detail = "regression-function", marker
                elif functions[marker]:
                    kind, detail = "regression-vacuous", f"{marker}: {'; '.join(functions[marker])}"
                elif marker not in executed:
                    kind, detail = "regression-not-executed", marker
                else:
                    continue
                missing.append({"control": control, "missing": detail, "kind": kind})
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
