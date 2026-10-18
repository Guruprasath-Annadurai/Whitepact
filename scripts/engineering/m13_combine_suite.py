# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Reject incomplete/mixed-source shards before accepting aggregate coverage."""

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def main():
    root = Path(sys.argv[1])
    expected_head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    plans = sorted(root.rglob("plan.json"))
    if len(plans) != 8:
        raise SystemExit(f"Expected 8 shard plans, got {len(plans)}")
    sources = set()
    hashes = set()
    indexes = set()
    selected = []
    failures = []
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    coverage_files = []
    skip_inventory = []
    collection_skips = []
    for path in plans:
        plan = json.loads(path.read_text())
        sources.add(plan["head"])
        hashes.add(plan["inventory_sha256"])
        indexes.add(plan["index"])
        directory = path.parent
        skip_inventory.extend(json.loads((directory / "skips.json").read_text())["skips"])
        collection_skips.extend(
            json.loads((directory / "collection-skips.json").read_text())["skips"]
        )
        result = json.loads((directory / "execution.json").read_text())
        if result["exit_code"] or not result["inventory_matches"]:
            failures.append(result)
        selected.extend(r["nodeid"] for r in json.loads((directory / "selected.json").read_text()))
        xml = ET.parse(directory / "results.xml")
        for suite in xml.iter("testsuite"):
            for key in totals:
                totals[key] += int(suite.get(key, "0"))
        coverage_files.append(str(directory / ".coverage"))
    first = json.loads(plans[0].read_text())
    inventory = json.loads((plans[0].parent / "inventory.json").read_text())
    expected = {r["nodeid"] for r in inventory}
    complete = (
        sources == {expected_head}
        and len(hashes) == 1
        and indexes == set(range(8))
        and len(selected) == len(set(selected))
        and set(selected) == expected
        and totals["tests"] == first["test_count"]
    )
    summary = {
        "head": expected_head,
        "complete_accounting": complete,
        "totals": totals,
        "failed_shards": failures,
        "inventory_count": len(expected),
        "skips": skip_inventory,
        "collection_skips": list({r["nodeid"]: r for r in collection_skips}.values()),
        "all_tests_passed": not failures
        and not any(totals[k] for k in ("failures", "errors", "skipped"))
        and not collection_skips,
    }
    Path("full-suite-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))
    if not complete:
        raise SystemExit("Missing, duplicate or mixed-source tests; coverage NOT ACCEPTED")
    subprocess.run(
        [sys.executable, "-m", "coverage", "combine", "--keep", *coverage_files], check=True
    )
    subprocess.run([sys.executable, "-m", "coverage", "json", "-o", "coverage.json"], check=True)
    subprocess.run([sys.executable, "-m", "coverage", "xml", "-o", "coverage.xml"], check=True)
    # Coverage remains measurable after failures, but never accepted as full-suite success.
    commands = [
        [sys.executable, "-m", "coverage", "report", "--fail-under=80"],
        [sys.executable, "scripts/check_branch_coverage.py", "--threshold", "80", "--fail"],
        [sys.executable, "scripts/check_statement_coverage.py", "--threshold", "90", "--fail"],
    ]
    codes = [subprocess.run(command, check=False).returncode for command in commands]
    return int(bool(failures or totals["failures"] or totals["errors"] or any(codes)))


if __name__ == "__main__":
    raise SystemExit(main())
