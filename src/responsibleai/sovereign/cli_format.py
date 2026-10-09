# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Shared human rendering for WhitePact CLI results.

JSON mode stays a deterministic dump of the same payload. Human mode
uses this module so commands do not each invent a formatter.
"""

from __future__ import annotations

from typing import Any

_PRIORITY_KEYS = (
    "disposition",
    "status",
    "decision",
    "result",
    "organization_id",
    "identity_id",
    "evidence_id",
    "approval_id",
    "valid",
    "zero_effect",
    "executed",
    "verification",
    "verification_state",
)


def _summarize(value: Any) -> str:
    if isinstance(value, list):
        return f"{len(value)} item(s)"
    if isinstance(value, dict):
        return f"{len(value)} field(s)"
    text = str(value)
    if len(text) > 180:
        return text[:177] + "..."
    return text


def _render_checks(checks: list[Any]) -> list[str]:
    lines: list[str] = []
    for item in checks:
        if not isinstance(item, dict):
            lines.append(f"- {_summarize(item)}")
            continue
        name = str(item.get("name") or "check")
        result = str(item.get("result") or "INFO")
        detail = item.get("detail") or ""
        suffix = f" — {detail}" if detail else ""
        lines.append(f"[{result}] {name}{suffix}")
    return lines


def _render_items(items: list[Any]) -> list[str]:
    lines: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            lines.append(f"- {_summarize(item)}")
            continue
        kind = item.get("kind") or item.get("code") or "item"
        message = item.get("message") or item.get("summary") or item.get("detail") or ""
        lines.append(f"- {kind}: {message}".rstrip())
    return lines


def render_human(data: object) -> str:
    """Concise multi-line text for a command payload. Never empty for a dict."""
    if data is None:
        return "No result."
    if not isinstance(data, dict):
        return str(data)

    lines: list[str] = []
    summary = data.get("human_summary")
    if isinstance(summary, str) and summary.strip():
        lines.append(summary.strip())

    for key in _PRIORITY_KEYS:
        if key not in data:
            continue
        value = data[key]
        if value in (None, "", [], {}):
            continue
        lines.append(f"{key}: {value}")

    checks = data.get("checks")
    if isinstance(checks, list) and checks:
        lines.append("checks:")
        lines.extend(_render_checks(checks))

    items = data.get("items")
    if isinstance(items, list) and items:
        lines.append("explanation:")
        lines.extend(_render_items(items))

    stages = data.get("stages")
    if isinstance(stages, list) and stages:
        lines.append(f"trace stages: {len(stages)}")
        lines.extend(_render_items(stages[:8]))

    graph = data.get("graph")
    if isinstance(graph, dict):
        nodes = graph.get("nodes") or []
        edges = graph.get("edges") or []
        node_count = len(nodes) if isinstance(nodes, list) else 0
        edge_count = len(edges) if isinstance(edges, list) else 0
        lines.append(f"authority graph: {node_count} nodes, {edge_count} edges")

    hints = data.get("envelope_hints")
    if isinstance(hints, list):
        for hint in hints:
            if hint:
                lines.append(f"hint: {hint}")

    cases = data.get("cases")
    if isinstance(cases, list):
        failed = sum(1 for case in cases if isinstance(case, dict) and case.get("status") == "FAIL")
        lines.append(f"cases: {len(cases)} ({failed} failed)")

    subjects = data.get("reconstruction") or data.get("subjects")
    if isinstance(subjects, list):
        for subject in subjects[:5]:
            if not isinstance(subject, dict):
                continue
            raw_integrity = subject.get("integrity")
            integrity = raw_integrity if isinstance(raw_integrity, dict) else {}
            digest = str(integrity.get("hash") or "")
            short = digest[:12] if digest else "none"
            lines.append(
                "evidence "
                f"{subject.get('evidence_id')}: decision {subject.get('decision')} "
                f"identity {subject.get('identity_id')} hash {short}"
            )
    explanation = data.get("explanation")
    if isinstance(explanation, list):
        for item in explanation[:5]:
            if isinstance(item, dict) and item.get("summary"):
                lines.append(str(item["summary"]))

    errors = data.get("errors")
    if isinstance(errors, list) and errors:
        lines.append("errors:")
        for err in errors[:8]:
            lines.append(f"- {err}")

    facts = data.get("facts")
    if isinstance(facts, list):
        lines.append(f"drift facts: {len(facts)}")
        for fact in facts[:6]:
            if isinstance(fact, dict):
                lines.append(f"- {fact.get('code')}: {fact.get('message')}")

    steps = data.get("steps")
    if isinstance(steps, list):
        lines.append(f"steps: {len(steps)}")

    if data.get("error") and "error:" not in "\n".join(lines):
        lines.append(f"error: {data['error']}")
    reason = data.get("reason")
    if reason and f"reason: {reason}" not in lines:
        lines.append(f"reason: {reason}")

    if not lines:
        lines.append("result:")
        for key, value in data.items():
            lines.append(f"  {key}: {_summarize(value)}")
    return "\n".join(lines)


def failure_line(data: object) -> str | None:
    """One actionable diagnostic for stderr. None when the payload is a success."""
    if not isinstance(data, dict):
        return None
    if data.get("error"):
        detail = data.get("reason") or data.get("message")
        if detail and detail != data["error"]:
            return f"{data['error']}: {detail}"
        return str(data["error"])
    checks = data.get("checks")
    if isinstance(checks, list):
        for item in checks:
            if isinstance(item, dict) and item.get("result") == "FAIL":
                name = item.get("name") or "check"
                detail = item.get("detail") or "failed"
                return f"{name}: {detail}"
    disposition = str(data.get("disposition") or "").upper()
    if disposition in {"REJECTED", "UNAVAILABLE", "INVALID_INPUT", "INTERNAL_ERROR", "DENY"}:
        return str(data.get("reason") or data.get("message") or disposition)
    return None
