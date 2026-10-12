# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Machine-checkable parts of the public MCP/plugin directory requirements, applied to the advertised tools.

Source for the rules (read 2026-10-11, re-read before every submission; they change):
https://developers.openai.com/plugins/plugin-guidelines  ("MCP requirements": clear names, descriptions that
match behaviour, explicit readOnly/destructive/openWorld booleans, minimal inputs, no model-steering text,
no generic executor, one operation per tool).

Passing this is a precondition for a review, not a prediction of acceptance and not a statement that any
directory has accepted WhitePact.
"""

from __future__ import annotations

import re

import pytest

from responsibleai.mcp.tools import TOOL_DEFS

ADVERTISED = [t for t in TOOL_DEFS if t.name != "test.counter.increment"]

STEERING = re.compile(
    r"\b(best|official|pick me|prefer(red)?|always use|must use|instead of|better than|only tool|"
    r"ignore (all |any )?(previous|prior)|do not use (any )?other|you must call)\b",
    re.I,
)
PRICING = re.compile(r"\b(free trial|discount|per month|\$\d|pricing|subscription)\b", re.I)
CONVERSATION_INPUTS = re.compile(
    r"^(conversation|conversation_history|chat_history|history|transcript|messages|prior_turns)$",
    re.I,
)
NAME = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


@pytest.mark.parametrize("tool", ADVERTISED, ids=lambda t: t.name)
def test_each_tool_meets_the_published_tool_definition_rules(tool) -> None:
    assert NAME.fullmatch(tool.name), tool.name
    assert tool.title and len(tool.title) >= 5, "a human-readable title is required"
    description = tool.description or ""
    assert len(description) >= 60, "descriptions must say what the tool does, when, and its limits"
    assert not STEERING.search(description), "descriptions must not steer model selection"
    assert not PRICING.search(description), "descriptions must not advertise pricing"
    hints = tool.annotations
    assert hints is not None
    for hint in ("readOnlyHint", "destructiveHint", "openWorldHint"):
        assert isinstance(getattr(hints, hint), bool), f"{hint} must be an explicit boolean"
    if hints.readOnlyHint:
        assert hints.destructiveHint is False
    schema = tool.inputSchema
    assert schema.get("type") == "object"
    for field in schema.get("properties", {}):
        assert not CONVERSATION_INPUTS.match(field), f"{field}: do not request conversation context"


def test_tool_names_are_unique_and_none_is_a_generic_executor() -> None:
    names = [t.name for t in ADVERTISED]
    assert len(names) == len(set(names))
    for tool in ADVERTISED:
        assert not re.search(r"(execute|run|invoke|call)_?(any|tool|command|operation)", tool.name)
        props = tool.inputSchema.get("properties", {})
        assert not ({"tool_name", "operation", "command", "method"} & set(props)), tool.name


def test_every_advertised_tool_is_read_only_and_says_so_truthfully() -> None:
    """The advertised surface is analysis only; nothing here changes external state. A tool that ever
    gains a write must flip its hint AND appear in the directory review notes."""
    assert all(t.annotations.readOnlyHint for t in ADVERTISED)


def test_the_test_fixture_is_never_advertised() -> None:
    from responsibleai.mcp.tools import production_tool_count

    assert production_tool_count() == len(ADVERTISED)


def test_the_incident_record_tool_does_not_claim_to_store_anything() -> None:
    tool = next(t for t in ADVERTISED if t.name == "rai_incident_log")
    assert "do not store" in tool.description.lower()
