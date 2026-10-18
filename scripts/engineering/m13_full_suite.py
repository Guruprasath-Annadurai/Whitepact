# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Accounted file-isolated CI shards; timeout and incomplete evidence are failures."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard", type=int, required=True)
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 0 <= args.shard < args.count:
        parser.error("invalid shard")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, M13_COLLECTION_FILE=str(out / "inventory.json"))
    collect = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "--collect-only",
        "-q",
        "-o",
        "addopts=",
        "-p",
        "scripts.engineering.m13_suite_inventory",
    ]
    with (out / "collection.log").open("w") as log:
        result = subprocess.run(
            collect, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180, check=False
        )
    if result.returncode:
        raise SystemExit("Collection failed; no incomplete inventory is accepted")
    inventory = json.loads((out / "inventory.json").read_text())
    nodeids = [row["nodeid"] for row in inventory]
    if len(nodeids) != len(set(nodeids)) or not nodeids:
        raise SystemExit("Empty or duplicate test inventory")
    counts = Counter(node.split("::", 1)[0] for node in nodeids)
    # Keep each file together. Greedy deterministic balancing by collected case
    # count avoids splitting module fixtures or sharing databases across jobs.
    shards = [[] for _ in range(args.count)]
    weights = [0] * args.count
    for filename, count in sorted(counts.items(), key=lambda row: (-row[1], row[0])):
        index = min(range(args.count), key=lambda i: (weights[i], i))
        shards[index].append(filename)
        weights[index] += count
    plan = {
        "head": git("rev-parse", "HEAD"),
        "tree": git("rev-parse", "HEAD^{tree}"),
        "python": sys.version,
        "inventory_sha256": hashlib.sha256(
            json.dumps(inventory, sort_keys=True).encode()
        ).hexdigest(),
        "test_count": len(nodeids),
        "files": len(counts),
        "weights": weights,
        "shards": shards,
        "index": args.shard,
    }
    (out / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    env["M13_COLLECTION_FILE"] = str(out / "selected.json")
    env["WHITEPACT_QUALIFICATION_SKIP_LOG"] = str(out / "skips.json")
    env["COVERAGE_FILE"] = str(out / ".coverage")
    command = [
        sys.executable,
        "-m",
        "pytest",
        *shards[args.shard],
        "-o",
        "addopts=",
        "-p",
        "scripts.engineering.m13_suite_inventory",
        "--timeout=120",
        "--timeout-method=thread",
        "-o",
        "faulthandler_timeout=90",
        "--cov=src/responsibleai",
        "--cov=src/biasbuster",
        "--cov=src/privacylabel",
        "--cov-branch",
        "--cov-report=",
        "--junitxml=" + str(out / "results.xml"),
        "--durations=30",
        "-vv",
        "-ra",
        "--tb=short",
    ]
    started = time.monotonic()
    code = 124
    try:
        with (out / "tests.log").open("w") as log:
            code = subprocess.run(
                command, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=1500, check=False
            ).returncode
    except subprocess.TimeoutExpired:
        pass
    expected = sorted(n for n in nodeids if n.split("::", 1)[0] in shards[args.shard])
    selected_path = out / "selected.json"
    actual = (
        sorted(row["nodeid"] for row in json.loads(selected_path.read_text()))
        if selected_path.exists()
        else []
    )
    summary = {
        "exit_code": code,
        "seconds": time.monotonic() - started,
        "inventory_matches": expected == actual,
        "expected": len(expected),
        "selected": len(actual),
        "head": plan["head"],
        "shard": args.shard,
    }
    (out / "execution.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))
    return code if code else (0 if expected == actual else 2)


if __name__ == "__main__":
    raise SystemExit(main())
