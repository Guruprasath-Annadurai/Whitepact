#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Actual customer ceremony through root/consent; fresh PostgreSQL, HTTP and Chromium."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
from contextlib import aclosing
from pathlib import Path

from scripts.engineering.m13i1_customer_journey import serve
from scripts.engineering.m13i2_customer_journey import configured_settings
from scripts.engineering.m13i3_browser_journey import git_identity
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from tests.pg_test_url import isolated_pg_url

import responsibleai.dashboard.app as dashboard
from responsibleai.db.migrate import _migration_env, _run_alembic


def validate_evidence(result: dict) -> None:
    """Reject incomplete or falsely successful browser receipts."""
    stages = result.get("stages", [])
    phases = [stage.get("phase") for stage in stages]
    if len(phases) != 24 or len(set(phases)) != 24:
        raise ValueError("Customer receipt requires 24 distinct stages")
    if result.get("authority_seeded") is not False:
        raise ValueError("Seeded authority is not customer acceptance")
    statuses = [stage.get("status") for stage in stages]
    if any(status not in {"PASS", "FAIL", "BLOCKED", "NOT_EXECUTED"} for status in statuses):
        raise ValueError("Unknown customer stage status")
    expected = (
        "FAIL"
        if "FAIL" in statuses
        else "PASS"
        if all(status == "PASS" for status in statuses)
        else "BLOCKED"
    )
    if result.get("acceptance") != expected:
        raise ValueError("Customer verdict contradicts stage evidence")
    stopped = False
    for stage in stages:
        if stage["phase"] == "logout_session_invalidation":
            continue
        if stopped and stage["status"] == "PASS":
            raise ValueError("Privileged success after an unqualified boundary")
        stopped = stopped or stage["status"] != "PASS"


async def attempt() -> dict:
    mail = []
    delivery_secret, receipt_secret = secrets.token_urlsafe(32), secrets.token_urlsafe(32)

    async def deliver(request):
        if request.headers.get("authorization") != f"Bearer {delivery_secret}":
            return Response(status_code=403)
        mail.append(await request.json())
        return Response(status_code=204)

    async def receipt(request):
        if request.headers.get("authorization") != f"Bearer {receipt_secret}":
            return Response(status_code=403)
        return JSONResponse(mail[0]) if len(mail) == 1 else Response(status_code=409)

    root = Path(__file__).parents[2]
    implementation = Path(dashboard.__file__).resolve().parents[3]
    ini = implementation / "alembic.ini"
    if not ini.is_file():
        raise RuntimeError("Implementation migration configuration missing")
    async with aclosing(isolated_pg_url("wp_apex_customer")) as databases:
        async for database in databases:
            await _run_alembic(ini, _migration_env(database), "upgrade", "head")
            async with serve(
                Starlette(
                    routes=[
                        Route("/deliver", deliver, methods=["POST"]),
                        Route("/receipt", receipt),
                    ]
                )
            ) as mailbox:
                with configured_settings(
                    {
                        "database_url": database,
                        "auto_migrate": False,
                        "auth_enabled": True,
                        "api_keys": [],
                        "environment": "development",
                        "web_auth_dev_tokens": False,
                        "web_session_secure": False,
                        "web_verification_delivery_url": f"{mailbox}/deliver",
                        "web_verification_delivery_token": delivery_secret,
                    }
                ):
                    async with serve(dashboard.app) as origin:
                        config = {
                            "origin": origin,
                            "receiptUrl": f"{mailbox}/receipt",
                            "receiptSecret": receipt_secret,
                            "credentials": {
                                "full_name": "Actual APEX Customer",
                                "email": f"apex-{secrets.token_hex(6)}@example.com",
                                "password": f"Apex-Local-{secrets.token_urlsafe(24)}-42!",
                            },
                        }
                        process = await asyncio.create_subprocess_exec(
                            "node",
                            str(root / "tests/js/m13-apex-customer.mjs"),
                            stdin=asyncio.subprocess.PIPE,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                            env={
                                key: os.environ[key]
                                for key in ("PATH", "HOME", "TMPDIR", "PLAYWRIGHT_BROWSERS_PATH")
                                if key in os.environ
                            },
                        )
                        try:
                            stdout, _stderr = await asyncio.wait_for(
                                process.communicate(json.dumps(config).encode()), 180
                            )
                            if process.returncode:
                                raise RuntimeError("Browser failed; private diagnostics withheld")
                            result = json.loads(stdout)
                            validate_evidence(result)
                            result["implementation_git"] = git_identity(implementation)
                            result["harness_git"] = git_identity(root)
                            result["fresh_postgresql"] = True
                            result["migration_configuration"] = str(ini)
                            return result
                        finally:
                            if process.returncode is None:
                                process.kill()
                                await process.wait()
    raise RuntimeError("Disposable PostgreSQL was not created")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    try:
        evidence = asyncio.run(attempt())
    except Exception as error:
        evidence = {"acceptance": "FAIL", "error_type": type(error).__name__}
    args.report.write_text(json.dumps(evidence, indent=2) + "\n")
    raise SystemExit(0 if evidence.get("acceptance") == "PASS" else 2)
