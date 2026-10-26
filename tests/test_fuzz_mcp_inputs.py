# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Property-based fuzzing of the hosted MCP input boundary.

Two pure functions sit on the trust boundary and must be total (never raise, never 500) and
conservative (accept only what the schema allows): the JSON-RPC body pre-validator and the
authority-tool argument validator. Hypothesis generates adversarial input far outside the examples
in the hand-written tests. This is bounded property testing, not coverage-guided fuzzing: it has no
corpus, no instrumentation feedback and a fixed example budget per run.
"""

from __future__ import annotations

import json

from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from responsibleai.mcp.authority_tools import (
    AUTHORITY_TOOL_NAMES,
    DEFAULT_PAGE_SIZE,
    MAX_CURSOR,
    MAX_PAGE_SIZE,
    _validate_arguments,
)
from responsibleai.mcp.server import MAX_MCP_REQUEST_BYTES, _reject_malformed_json_rpc_body

_json_leaf = st.none() | st.booleans() | st.integers() | st.floats(allow_nan=True) | st.text()
_json_value = st.recursive(
    _json_leaf,
    lambda inner: (
        st.lists(inner, max_size=4) | st.dictionaries(st.text(max_size=20), inner, max_size=4)
    ),
    max_leaves=12,
)
_FUZZ = settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@_FUZZ
@given(st.binary(max_size=4096))
def test_body_prevalidator_is_total_and_only_accepts_valid_utf8_json(body: bytes) -> None:
    rejection = _reject_malformed_json_rpc_body(body)
    if rejection is None:
        json.loads(body.decode("utf-8"))  # accepted bodies really are UTF-8 JSON
    else:
        assert rejection.status_code in {400, 413}


def test_body_prevalidator_rejects_over_limit_before_parsing() -> None:
    response = _reject_malformed_json_rpc_body(b" " * (MAX_MCP_REQUEST_BYTES + 1))
    assert response is not None and response.status_code == 413


@_FUZZ
@given(
    st.sampled_from(sorted(AUTHORITY_TOOL_NAMES)),
    st.dictionaries(st.text(max_size=24), _json_value, max_size=6),
)
def test_authority_argument_validator_is_total(name: str, arguments: dict) -> None:
    result = _validate_arguments(name, arguments)
    assert result is None or result["error"] == "invalid_arguments"


_ALLOWED = {
    "whitepact_policy_status": set(),
    "whitepact_simulate_policy": {"action_type", "target", "risk_tier"},
    "whitepact_list_pending_approvals": {"limit", "cursor"},
    "whitepact_verify_evidence": {"expected_head_hash"},
}


@_FUZZ
@given(
    st.sampled_from(sorted(AUTHORITY_TOOL_NAMES)),
    st.dictionaries(st.text(max_size=24), _json_value, max_size=6),
)
def test_accepted_arguments_never_contain_an_unknown_key(name: str, arguments: dict) -> None:
    if _validate_arguments(name, arguments) is None:
        assert set(arguments) <= _ALLOWED[name]


@_FUZZ
@given(_json_value, _json_value)
def test_pagination_values_outside_bounds_are_always_rejected(
    limit: object, cursor: object
) -> None:
    args = {"limit": limit, "cursor": cursor}
    if _validate_arguments("whitepact_list_pending_approvals", args) is None:
        assert isinstance(limit, int) and not isinstance(limit, bool)
        assert 1 <= limit <= MAX_PAGE_SIZE
        assert isinstance(cursor, str) and cursor.isdigit() and int(cursor) <= MAX_CURSOR
    assert DEFAULT_PAGE_SIZE <= MAX_PAGE_SIZE


@_FUZZ
@given(st.text(max_size=300), st.text(max_size=300))
@example(
    "x\n", "y"
)  # `$` matches before a trailing newline: this was accepted before the fullmatch fix
@example("x", "y\n")
@example("x\r\n", "y")
def test_simulation_inputs_accept_only_the_documented_token_alphabet(
    action: str, target: str
) -> None:
    import re

    result = _validate_arguments(
        "whitepact_simulate_policy", {"action_type": action, "target": target}
    )
    pattern = re.compile(r"^[A-Za-z0-9_.:\-/]{1,128}$")
    ok = bool(pattern.fullmatch(action)) and bool(pattern.fullmatch(target))
    assert (result is None) == ok


@example("0" * 64 + "\n")
@example("\n" + "0" * 64)
@_FUZZ
@given(st.text(max_size=80))
def test_expected_head_hash_is_exactly_64_lowercase_hex(value: str) -> None:
    import re

    result = _validate_arguments("whitepact_verify_evidence", {"expected_head_hash": value})
    assert (result is None) == bool(re.fullmatch(r"[0-9a-f]{64}", value))
