#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Actual disposable PostgreSQL + HTTP + Chromium CDP customer ceremony attempt."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import subprocess
from pathlib import Path

from scripts.engineering.m13_stage3_customer_fixture import isolated_provisioning_controller
from scripts.engineering.m13i1_customer_journey import serve
from scripts.engineering.m13i2_customer_journey import configured_settings, isolated_startup_store_b
from sqlalchemy import text
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from tests.pg_test_url import isolated_pg_url

import responsibleai.dashboard.app as dashboard
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic


def git_identity(path: Path) -> dict:
    values = subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD", "HEAD^{tree}"], text=True
    ).splitlines()
    dirty = subprocess.check_output(["git", "-C", str(path), "status", "--porcelain"], text=True)
    return {"commit": values[0], "tree": values[1], "clean": not bool(dirty)}


def validate_report(result: dict) -> None:
    if result.get("kind") != "ACTUAL_POSTGRESQL_HTTP_CHROMIUM_WEBAUTHN_EMULATOR":
        raise ValueError("Unexpected browser evidence type")
    if result.get("acceptance") != "BLOCKED":
        raise ValueError("Partial ceremonies cannot qualify the golden journey")
    phases = result.get("phases")
    if not isinstance(phases, list) or not phases:
        raise ValueError("Browser phase evidence is missing")
    names = set()
    confirmed = set()
    for phase in phases:
        name = phase.get("phase")
        if not isinstance(name, str) or name in names:
            raise ValueError("Browser phase identity is invalid")
        names.add(name)
        if phase.get("result") not in {"CONFIRMED", "BLOCKED"}:
            raise ValueError("Unconfirmed browser evidence")
        if phase["result"] == "CONFIRMED":
            confirmed.add(name)
    if "server_assertion_verification" in confirmed and not {
        "server_registration_verification",
        "browser_generated_assertion",
    }.issubset(confirmed):
        raise ValueError("Assertion verification lacks its actual prerequisite evidence")
    if not {"root_authority", "controlled_execution", "authority_revocation"}.issubset(
        result.get("not_executed", [])
    ):
        raise ValueError("Unexecuted privileged stages must remain explicit")


WEBAUTHN_COMPONENT_PHASES = frozenset(
    {
        "empty_chromium_virtual_authenticator",
        "signup",
        "genuine_mail_verification",
        "password_login",
        "organization_onboarding",
        "authenticated_owner_session",
        "recorded_authority_snapshot",
        "registration_challenge",
        "browser_origin_binding",
        "browser_generated_registration",
        "request_registration_step_up",
        "server_registration_verification",
        "authentication_challenge",
        "browser_generated_assertion",
        "server_assertion_verification",
        "persisted_passkey_inventory",
        "session_cleanup_logout",
    }
)


def webauthn_component_qualified(result: dict) -> bool:
    """Qualify actual ceremony evidence, never the unexecuted customer chain."""
    validate_report(result)
    phases = {phase["phase"]: phase for phase in result["phases"]}
    return WEBAUTHN_COMPONENT_PHASES.issubset(phases) and all(
        phase["result"] == "CONFIRMED" for phase in phases.values()
    )


async def attempt(*, authorized_bootstrap: bool = False) -> dict:
    mail = []
    delivery_secret = secrets.token_urlsafe(32)
    receipt_secret = secrets.token_urlsafe(32)

    async def deliver(request):
        if request.headers.get("authorization") != f"Bearer {delivery_secret}":
            return Response(status_code=403)
        mail.append(await request.json())
        return Response(status_code=204)

    async def receipt(request):
        if request.headers.get("authorization") != f"Bearer {receipt_secret}":
            return Response(status_code=403)
        return JSONResponse(mail[0]) if len(mail) == 1 else Response(status_code=409)

    async for database in isolated_pg_url("wp_m13i3_browser"):
        ini = _find_alembic_ini()
        if ini is None:
            raise RuntimeError("Migration configuration unavailable")
        await _run_alembic(ini, _migration_env(database), "upgrade", "head")
        async with serve(
            Starlette(
                routes=[Route("/deliver", deliver, methods=["POST"]), Route("/receipt", receipt)]
            )
        ) as mailbox:
            changes = {
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
            with isolated_startup_store_b(), configured_settings(changes):
                async with (
                    isolated_provisioning_controller(
                        database, authorized_bootstrap=authorized_bootstrap
                    ) as provisioner,
                    serve(dashboard.app) as origin,
                ):
                    config = {
                        "origin": origin,
                        "receiptUrl": f"{mailbox}/receipt",
                        "receiptSecret": receipt_secret,
                        "credentials": {
                            "full_name": "Actual I3 Browser Customer",
                            "email": f"i3-{secrets.token_hex(6)}@example.com",
                            "password": f"I3-Local-{secrets.token_urlsafe(24)}-42!",
                        },
                    }
                    process = await asyncio.create_subprocess_exec(
                        "node",
                        str(Path(__file__).parents[2] / "tests/js/m13i3-real-webauthn.mjs"),
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
                            process.communicate(json.dumps(config).encode()), 150
                        )
                        if process.returncode != 0:
                            raise RuntimeError(
                                "Browser process failed; private diagnostics withheld"
                            )
                        result = json.loads(stdout)
                        validate_report(result)
                        result["fresh_postgresql_migration"] = "CONFIRMED"
                        result["implementation_git"] = git_identity(
                            Path(dashboard.__file__).parents[3]
                        )
                        result["harness_git"] = git_identity(Path(__file__).parents[2])
                        readiness = provisioner.provider.get_readiness_state()
                        result["store_b_readiness"] = readiness.value if readiness else None
                        async with provisioner.engine.raw.connect() as connection:
                            result["authority_counts"] = {
                                table: await connection.scalar(
                                    text(f"SELECT count(*) FROM {table}")
                                )
                                for table in (
                                    "organizations",
                                    "governance_root_authority_records",
                                    "governance_execution_authorizations",
                                    "runtime_execution_attempts",
                                )
                            }
                        return result
                    finally:
                        if process.returncode is None:
                            process.kill()
                            await process.wait()
    raise RuntimeError("Disposable PostgreSQL iteration did not run")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="Write redacted structured runtime evidence")
    parser.add_argument("--authorized-disposable-bootstrap", action="store_true")
    parser.add_argument(
        "--webauthn-component",
        action="store_true",
        help="Qualify only the actual 17-phase ceremony; full customer acceptance stays BLOCKED",
    )
    args = parser.parse_args()
    try:
        result = asyncio.run(attempt(authorized_bootstrap=args.authorized_disposable_bootstrap))
    except Exception as error:
        result = {
            "acceptance": "BLOCKED",
            "error_type": type(error).__name__,
            "production": "GLOBAL PRODUCTION NO-GO",
        }
    component_passed = False
    if args.webauthn_component:
        try:
            component_passed = webauthn_component_qualified(result)
        except ValueError:
            pass
        result["qualification_scope"] = "WEBAUTHN_COMPONENT_ONLY"
        result["component_acceptance"] = "PASS" if component_passed else "BLOCKED"
    serialized = json.dumps(result, indent=2)
    if args.report:
        args.report.write_text(serialized + "\n")
    print(serialized)
    raise SystemExit(0 if component_passed else 2)
