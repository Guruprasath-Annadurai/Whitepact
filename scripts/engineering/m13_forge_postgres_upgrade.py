#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Compare published migrations on a disposable PostgreSQL database; no authority fixtures."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from contextlib import aclosing
from pathlib import Path

import asyncpg
from tests.pg_test_url import isolated_pg_url

MIGRATE = """
import asyncio, os
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
ini = _find_alembic_ini()
if ini is None: raise RuntimeError('Migration configuration missing')
asyncio.run(_run_alembic(ini, _migration_env(os.environ['FORGE_TEST_DATABASE_URL']), 'upgrade', 'head'))
"""


def identity(checkout: Path) -> dict:
    commit, tree = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD", "HEAD^{tree}"], text=True
    ).splitlines()
    dirty = subprocess.check_output(
        ["git", "-C", str(checkout), "status", "--porcelain"], text=True
    )
    return {"commit": commit, "tree": tree, "clean": not bool(dirty)}


async def migrate(checkout: Path, url: str) -> None:
    env = dict(os.environ, PYTHONPATH=str(checkout / "src"), FORGE_TEST_DATABASE_URL=url)
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        MIGRATE,
        cwd=checkout,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        await asyncio.wait_for(process.communicate(), 120)
        if process.returncode:
            raise RuntimeError("Published migration invocation failed")
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


async def schema(url: str) -> dict:
    connection = await asyncpg.connect(
        url.replace("postgresql+asyncpg://", "postgresql://"), timeout=10, command_timeout=10
    )
    try:
        return {
            "revision": await connection.fetchval("SELECT version_num FROM alembic_version"),
            "required_column": await connection.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='trust_fabric_bootstrap_records' "
                "AND column_name='require_passkey_stepup')"
            ),
        }
    finally:
        await connection.close(timeout=10)


async def probe(before: Path, after: Path) -> dict:
    async with aclosing(isolated_pg_url("wp_forge_upgrade")) as databases:
        async for url in databases:
            await migrate(before, url)
            baseline = await schema(url)
            await migrate(after, url)
            upgraded = await schema(url)
            return {
                "kind": "ACTUAL_POSTGRESQL_EXISTING_HEAD_UPGRADE",
                "before": identity(before),
                "after": identity(after),
                "harness": identity(Path(__file__).parents[2]),
                "baseline_schema": baseline,
                "upgraded_schema": upgraded,
                "result": "PASS" if upgraded["required_column"] else "BLOCKED",
                "authority_seeded": False,
                "production": "GLOBAL PRODUCTION NO-GO",
            }
    raise RuntimeError("Disposable PostgreSQL was not created")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = asyncio.run(probe(args.before.resolve(), args.after.resolve()))
    except Exception as error:
        report = {"result": "FAIL", "error_type": type(error).__name__}
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    raise SystemExit(0 if report["result"] == "PASS" else 2)
