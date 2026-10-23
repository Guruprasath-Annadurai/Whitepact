# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Pinned originals and assertion equivalence for authorized setup modernization."""

import ast
import copy
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = "e156b59a39ad926344474233ef02dddd82e9ce0a"
BLOBS = {
    "test_mcp_governance_dispatch.py": "552aeca8ff32d4afbbdf14362b5c48ab05ddbb71",
    "test_db_migrate.py": "b02e95b831cf0361a505af4d0a5e83b82f55efaa",
    "test_m13_apex_directory.py": "41a618f5b953d1842187770801df056be17fe6a4",
    "test_m13_apex_organization.py": "96011b14f39b1f60ded429c46475c14f777b0ebc",
    "test_m13_apex_sse_binding.py": "59c57a36e09dabe5561f8155098d781c8b789aed",
    "test_sovereign_authority.py": "808a5e5b7863ab24d74e1684ccbe8071f3b403cf",
    "test_stage3_controller_postgres.py": "e3074ba95144fbcb4a2a18de561a3162098a208f",
}


def original_source(name):
    blob = subprocess.run(
        ["git", "rev-parse", f"{ORIGINAL}:tests/{name}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    ).stdout.strip()
    assert blob == BLOBS[name]
    return subprocess.run(
        ["git", "cat-file", "blob", blob],
        cwd=ROOT,
        check=True,
        capture_output=True,
        timeout=20,
    ).stdout


class NormalizeFixtureIds(ast.NodeTransformer):
    """Only controller-generated fixture labels replace historical literal IDs."""

    def visit_Name(self, node):
        if node.id in {"own", "tenant"}:
            return ast.Constant("apex-org")
        if node.id == "other":
            return ast.Constant("other-org")
        return node


def test_assertions(source, *, normalize=False):
    result = {}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef) and node.name.startswith(
            "test_"
        ):
            assertions = [
                copy.deepcopy(item) for item in ast.walk(node) if isinstance(item, ast.Assert)
            ]
            if normalize:
                assertions = [NormalizeFixtureIds().visit(item) for item in assertions]
            result[node.name] = [ast.dump(item, include_attributes=False) for item in assertions]
    return result


# This is an analysis helper, not a pytest test.
test_assertions.__test__ = False


@pytest.mark.parametrize("name", BLOBS)
def test_original_source_and_all_security_assertions_preserved(name):
    old = original_source(name)
    current = (ROOT / "tests" / name).read_bytes()
    if name == "test_db_migrate.py":
        before, after = test_assertions(old), test_assertions(current)
        # These three tests explicitly change transport from unsupported SQLite
        # to actual PostgreSQL. Do not misrepresent their transport assertions
        # as AST-identical; every other historical assertion remains exact.
        successors = {
            "test_fresh_database_reaches_head",
            "test_running_twice_is_idempotent",
            "test_unique_temp_dbs_do_not_interfere",
        }
        assert set(after) == set(before) | {
            "test_sqlite_current_head_remains_explicitly_unsupported"
        }
        for key, assertions in before.items():
            if key not in successors:
                assert after[key] == assertions
        for key in ("test_fresh_database_reaches_head", "test_running_twice_is_idempotent"):
            # Exact canonical-head equality, not a minimum version, remains.
            assert before[key][0] == after[key][0]
        assert (
            before["test_fresh_database_reaches_head"][1:]
            == after["test_fresh_database_reaches_head"][1:]
        )
        return
    normalize = name in {"test_m13_apex_directory.py", "test_m13_apex_organization.py"}
    assert test_assertions(current, normalize=normalize) == test_assertions(old)


@pytest.mark.parametrize("change", ["assertion", "timeout", "denial"])
def test_changed_security_assertion_is_detected(change):
    source = "async def test_boundary():\n    assert elapsed < 2.0\n    assert status == 403\n"
    mutated = {
        "assertion": source.replace("status == 403", "status == 200"),
        "timeout": source.replace("2.0", "20.0"),
        "denial": source.replace("    assert status == 403\n", ""),
    }[change]
    assert test_assertions(source) != test_assertions(mutated)


def test_approved_root_successor_split_preserves_every_other_reproducer():
    path = "scripts/engineering/reproducers/test_m13_corrective_authority.py"
    blob = "30a18aa17fc2aa0d67bb7ca5a7f9e757985192f3"
    historical = subprocess.run(
        ["git", "rev-parse", f"{ORIGINAL}:{path}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    ).stdout.strip()
    assert historical == blob
    old = subprocess.run(
        ["git", "cat-file", "blob", blob],
        cwd=ROOT,
        check=True,
        capture_output=True,
        timeout=20,
    ).stdout
    current = (ROOT / path).read_bytes()
    before, after = test_assertions(old), test_assertions(current)
    evolved = "test_unverified_owner_cannot_activate_root_with_default_flags"
    successors = {
        "test_unverified_onboarding_successor_has_no_tenant_or_root",
        "test_unverified_after_provisioning_successor_has_no_root",
    }
    assert set(after) == set(before) | successors
    for name in before:
        if name != evolved:
            assert before[name] == after[name]
    # The original public ID still executes both distinctly named paths.
    function = next(
        node
        for node in ast.walk(ast.parse(current))
        if isinstance(node, ast.AsyncFunctionDef) and node.name == evolved
    )
    calls = [
        node.value.value.func.id
        for node in function.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Await)
    ]
    assert calls == [
        "_assert_never_verified_onboarding_denied",
        "_assert_revoked_verification_root_denied",
    ]
