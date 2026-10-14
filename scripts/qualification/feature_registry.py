# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Validate exact inventoried IDs and produce conservative, deterministic ledgers.

Evidence metadata is a checkable assertion, not independent qualification. This
validator never promotes source inspection, historical tests or CI to VERIFIED.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
from datetime import datetime
from pathlib import Path, PurePosixPath

STATUSES = {"VERIFIED", "IMPLEMENTED UNVERIFIED", "PARTIAL", "BLOCKED", "UNSUPPORTED", "NOT FOUND"}
KINDS = {
    "CUSTOMER FEATURE",
    "SECURITY CONTROL",
    "INTERNAL MECHANISM",
    "TEST",
    "INFRASTRUCTURE",
    "PLANNED",
}
REQUIRED = {
    "id",
    "title",
    "historical_status",
    "status",
    "kind",
    "source_paths",
    "symbols",
    "api_routes",
    "frontend_paths",
    "test_paths",
    "owner",
    "priority",
    "limitations",
    "acceptance_criteria",
    "overlap_ids",
    "implemented_behavior",
    "user_accessibility",
    "latest_qualification_commit",
    "test_evidence",
    "security_dependencies",
    "deployment_requirements",
    "symbol_mappings",
}


class RegistryError(ValueError):
    """Reject incomplete or misleading feature registries."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RegistryError("Duplicate registry JSON field")
        result[key] = value
    return result


def _invalid_constant(value):
    raise RegistryError("Non-finite registry JSON number")


def load_json(path: Path):
    """Read bounded, unambiguous metadata without echoing private input."""
    try:
        with path.open("rb") as stream:
            raw = stream.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise RegistryError("Registry JSON exceeds size limit")
        return json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except (OSError, UnicodeError, ValueError, RecursionError):
        raise RegistryError("Unreadable or invalid registry JSON") from None


def _path(value: str, root: Path, *, must_exist: bool = True) -> None:
    if not isinstance(value, str) or not value or "\\" in value:
        raise RegistryError("Invalid source path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in {"..", "."} for p in value.split("/")):
        raise RegistryError("Unsafe source path")
    resolved = (root / value).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise RegistryError("Source path escapes repository")
    if must_exist and not resolved.is_file():
        raise RegistryError(f"Source file not found: {value}")


def validate(registry: dict, root: Path) -> list[dict]:
    if not isinstance(registry, dict) or registry.get("schema_version") != 1:
        raise RegistryError("Unsupported registry schema")
    original = registry.get("original_inventory")
    entries = registry.get("entries")
    source = registry.get("original_inventory_source")
    _path(source, root)
    if not isinstance(original, list) or not isinstance(entries, list):
        raise RegistryError("Original inventory and entries required")
    if any(not isinstance(row, dict) for row in original):
        raise RegistryError("Original inventory must contain objects")
    input_rows = [
        (int(number), title)
        for number, title in re.findall(
            r"^(\d+)\. (.+)$", (root / source).read_text(), flags=re.MULTILINE
        )
    ]
    if input_rows != [(i, row.get("title")) for i, row in enumerate(original or [], 1)]:
        raise RegistryError("Registry original inventory differs from canonical input")
    if not isinstance(original, list) or not isinstance(entries, list):
        raise RegistryError("Original inventory and entries required")
    expected = list(range(1, 176))
    for collection in (original, entries):
        if any(not isinstance(row, dict) or type(row.get("id")) is not int for row in collection):
            raise RegistryError("Integer IDs required")
        if sorted(row["id"] for row in collection) != expected:
            raise RegistryError("Exactly one of each original ID 1 through 175 required")
    titles = {row["id"]: row.get("title") for row in original}
    if any(not isinstance(title, str) or not title.strip() for title in titles.values()):
        raise RegistryError("Original titles required")
    for row in entries:
        if not REQUIRED <= row.keys():
            raise RegistryError(f"Entry {row['id']} missing required fields")
        if row["title"] != titles[row["id"]]:
            raise RegistryError(f"Entry {row['id']} title changed")
        if row["status"] not in STATUSES or row["kind"] not in KINDS:
            raise RegistryError("Invalid status or classification")
        if row["priority"] not in {"P0", "P1", "P2", "P3"}:
            raise RegistryError("Invalid priority")
        for key in (
            "owner",
            "historical_status",
            "limitations",
            "acceptance_criteria",
            "implemented_behavior",
            "user_accessibility",
            "security_dependencies",
            "deployment_requirements",
        ):
            if not isinstance(row[key], str) or not row[key].strip():
                raise RegistryError(f"Nonempty {key} required")
        for key in (
            "source_paths",
            "symbols",
            "api_routes",
            "frontend_paths",
            "test_paths",
            "overlap_ids",
        ):
            if not isinstance(row[key], list):
                raise RegistryError(f"{key} must be a list")
        for key in ("source_paths", "frontend_paths", "test_paths"):
            for value in row[key]:
                _path(value, root)
        if not isinstance(row["symbol_mappings"], list):
            raise RegistryError("Typed symbol mappings required")
        for mapping in row["symbol_mappings"]:
            if (
                not isinstance(mapping, dict)
                or mapping.get("role") != "UNQUALIFIED_SOURCE_ASSOCIATION"
            ):
                raise RegistryError("Explicit unqualified source association required")
            _path(mapping.get("path"), root)
            if not isinstance(mapping.get("symbol"), str) or not mapping["symbol"]:
                raise RegistryError("Exact mapped symbol required")
        evidence = row["test_evidence"]
        if not isinstance(evidence, dict) or evidence.get("kind") not in {
            "SOURCE_ONLY",
            "FRESH_EXECUTED",
            "NONE",
        }:
            raise RegistryError("Explicit test evidence category required")
        if row["status"] != "VERIFIED" and (
            row["latest_qualification_commit"] is not None
            or evidence.get("kind") == "FRESH_EXECUTED"
        ):
            raise RegistryError("Unqualified entries cannot claim fresh executed qualification")
        if any(
            type(i) is not int or i not in expected or i == row["id"] for i in row["overlap_ids"]
        ):
            raise RegistryError("Invalid overlap ID")
        if row["status"] == "VERIFIED":
            proof = row.get("qualification")
            if not isinstance(proof, dict) or proof.get("kind") != "FRESH_EXECUTED":
                raise RegistryError(
                    "VERIFIED requires fresh executed evidence, not source/historical claims"
                )
            if not all(
                re.fullmatch(r"[0-9a-f]{40}", str(proof.get(k, ""))) for k in ("head", "tree")
            ):
                raise RegistryError("Exact qualification HEAD and TREE required")
            if proof.get("head") != registry.get("qualification_target_head"):
                raise RegistryError("Evidence must match current qualification target")
            if proof.get("tree") != registry.get("qualification_target_tree"):
                raise RegistryError("Evidence must match current qualification tree")
            if (
                row["latest_qualification_commit"] != proof["head"]
                or evidence.get("kind") != "FRESH_EXECUTED"
            ):
                raise RegistryError("Qualified entry evidence and latest commit must agree")
            if (
                type(proof.get("passed")) is not int
                or proof["passed"] < 1
                or proof.get("failed") != 0
            ):
                raise RegistryError("Successful actual test results required")
            if type(proof.get("skipped")) is not int or proof["skipped"] < 0:
                raise RegistryError("Exact skipped count required")
            try:
                stamp = datetime.fromisoformat(proof.get("executed_at", ""))
            except (TypeError, ValueError) as exc:
                raise RegistryError("Execution timestamp required") from exc
            if stamp.tzinfo is None:
                raise RegistryError("Timezone-aware execution timestamp required")
            if not proof.get("command") or not proof.get("scope"):
                raise RegistryError("Actual command and evidence scope required")
            _path(proof.get("artifact", ""), root)
            try:
                evidence = load_json(root / proof["artifact"])
            except (ValueError, OSError) as exc:
                raise RegistryError("Machine-readable executed evidence artifact required") from exc
            keys = (
                "kind",
                "head",
                "tree",
                "passed",
                "failed",
                "skipped",
                "executed_at",
                "command",
                "scope",
            )
            if not isinstance(evidence, dict) or any(
                evidence.get(key) != proof.get(key) for key in keys
            ):
                raise RegistryError("Qualification metadata differs from evidence artifact")
        elif row.get("qualification"):
            raise RegistryError("Non-VERIFIED entries cannot carry a qualification claim")
    return sorted(entries, key=lambda row: row["id"])


def generate(registry: dict, root: Path) -> tuple[str, str]:
    rows = validate(registry, root)
    stream = io.StringIO(newline="")
    columns = ["id", "title"] + sorted(set().union(*(row.keys() for row in rows)) - {"id", "title"})
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()

    def spreadsheet_cell(value):
        # CSV quoting does not stop spreadsheet formula evaluation. Escape only
        # this presentation; the original registry/title input remains exact.
        if isinstance(value, (list, dict)):
            value = json.dumps(value, sort_keys=True, separators=(",", ":"))
        if isinstance(value, str) and value:
            if value.lstrip().startswith(("=", "+", "-", "@")) or ord(value[0]) < 32:
                return "'" + value
        return value

    writer.writerows({key: spreadsheet_cell(value) for key, value in row.items()} for row in rows)
    lines = [
        "# WhitePact M12 feature acceptance matrix",
        "",
        "Historical status is unverified. Source mapping is not production qualification.",
        "",
        "| ID | Original title | Current status | Kind | Acceptance / limits |",
        "|---|---|---|---|---|",
    ]

    def escape(value):
        return str(value).replace("|", "\\|").replace("\n", "<br>")

    for row in rows:
        lines.append(
            "| "
            + " | ".join(escape(row[k]) for k in ("id", "title", "status", "kind"))
            + " | "
            + escape(row["acceptance_criteria"] + " / " + row["limitations"])
            + " |"
        )
    return stream.getvalue(), "\n".join(lines) + "\n"


def write_generated(registry: dict, root: Path) -> None:
    """Write only the two fixed public ledgers after validation and path checks."""
    outputs = generate(registry, root)
    root = root.resolve(strict=True)
    parent = root
    for part in ("docs", "m12"):
        parent = parent / part
        if parent.is_symlink() or not parent.resolve().is_relative_to(root):
            raise RegistryError("Generated output parent is unsafe")
        if parent.exists() and not parent.is_dir():
            raise RegistryError("Generated output parent is not a directory")
    names = ("WHITEPACT_M12_175_FEATURE_LEDGER.csv", "WHITEPACT_M12_FEATURE_ACCEPTANCE_MATRIX.md")
    paths = [parent / name for name in names]
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise RegistryError("Generated output path is unsafe")
        if path.exists() and not path.is_file():
            raise RegistryError("Generated output must be a regular file")
    # Check every output before changing either artifact. Runtime generation is
    # confined to an owned build directory; this is not an adversarial FS sandbox.
    parent.mkdir(parents=True, exist_ok=True)
    for path, content in zip(paths, outputs, strict=True):
        path.write_text(content, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--format", choices=("summary", "csv", "markdown"), default="summary")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-generated", action="store_true")
    mode.add_argument("--write-generated", action="store_true")
    args = parser.parse_args()
    data = load_json(args.registry)
    rows = validate(data, args.root)
    if args.write_generated:
        write_generated(data, args.root)
    if args.check_generated:
        outputs = generate(data, args.root)
        names = (
            "WHITEPACT_M12_175_FEATURE_LEDGER.csv",
            "WHITEPACT_M12_FEATURE_ACCEPTANCE_MATRIX.md",
        )
        for name, content in zip(names, outputs, strict=True):
            path = args.root / "docs/m12" / name
            if not path.is_file() or path.read_text() != content:
                raise RegistryError(f"Generated artifact stale: {name}")
    if args.format != "summary":
        print(generate(data, args.root)[0 if args.format == "csv" else 1], end="")
        return 0
    print(
        json.dumps(
            {
                "entries": len(rows),
                "statuses": {s: sum(r["status"] == s for r in rows) for s in sorted(STATUSES)},
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except (RegistryError, OSError, TypeError, KeyError):
        # Metadata, paths and parser messages can contain private input. Detailed
        # programmatic diagnostics remain available to local callers via validate.
        print(json.dumps({"status": "REJECTED", "error": "Invalid or unreadable feature registry"}))
        code = 2
    raise SystemExit(code)
