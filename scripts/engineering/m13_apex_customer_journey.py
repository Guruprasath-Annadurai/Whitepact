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
from contextlib import aclosing, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.engineering.m13i1_customer_journey import serve
from scripts.engineering.m13i2_customer_journey import configured_settings
from scripts.engineering.m13i3_browser_journey import git_identity
from sqlalchemy import func, select
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from tests.pg_test_url import isolated_pg_url

import responsibleai.dashboard.app as dashboard
from responsibleai.db.engine import (
    governance_consent_proofs,
    governance_root_authority_records,
    trust_fabric_principals,
    web_users,
)
from responsibleai.db.migrate import _migration_env, _run_alembic
from responsibleai.enterprise.runtime import get_enterprise_engine

PHASES = (
    "signup",
    "email_verification",
    "password_login",
    "organization_onboarding",
    "passkey_enrollment",
    "passkey_assertion_verification",
    "secure_elevated_session",
    "legitimate_identity_qualification",
    "explicit_customer_consent",
    "root_initiation",
    "root_proof_of_possession",
    "root_activation",
    "application_registration",
    "agent_registration",
    "capability_delegation",
    "policy_assignment",
    "judgment",
    "human_approval",
    "execution_grant",
    "controlled_execution",
    "evidence_verification",
    "revocation",
    "post_revocation_execution_attempt",
    "post_revocation_denial",
    "logout_session_invalidation",
)


@contextmanager
def isolated_startup_store_b():
    """Provision the fresh disposable journey's Store B, never recover an old store.

    The application server must be stopped before exit. The prior gate and its
    durable evidence are retained untouched; only this fresh database fixture
    receives a new provider. No READY write or recovery authority is supplied.
    """
    from responsibleai.data_governance.backup_defense import (
        get_restore_readiness_gate,
        set_restore_readiness_gate,
    )
    from responsibleai.environment import is_production

    if is_production():
        raise RuntimeError("Disposable onboarding requires an explicit nonproduction environment")
    original = get_restore_readiness_gate()
    keys = ("WHITEPACT_STORE_B_PATH", "WHITEPACT_STORE_B_KEY")
    previous = {key: os.environ.get(key) for key in keys}
    with TemporaryDirectory(prefix="whitepact-apex-store-b-") as directory:
        try:
            os.environ["WHITEPACT_STORE_B_PATH"] = str(Path(directory) / "lifecycle.sqlite3")
            os.environ["WHITEPACT_STORE_B_KEY"] = secrets.token_urlsafe(32)
            set_restore_readiness_gate(None)
            yield
        finally:
            set_restore_readiness_gate(original)
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def validate_evidence(result: dict) -> None:
    """Reject incomplete or falsely successful browser receipts."""
    stages = result.get("stages", [])
    phases = [stage.get("phase") for stage in stages]
    if phases != list(PHASES):
        raise ValueError("Customer receipt requires the exact 25 distinct stages in order")
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
    # Consent is stored by bootstrap completion, after initiation. Report order
    # follows the acceptance checklist; dependencies follow the actual contract.
    execution_order = (
        *PHASES[:8],
        "root_initiation",
        "root_proof_of_possession",
        "explicit_customer_consent",
        "root_activation",
        *PHASES[12:24],
    )
    state = {stage["phase"]: stage["status"] for stage in stages}
    for previous, current in zip(execution_order, execution_order[1:], strict=False):
        if state[current] == "PASS" and state[previous] != "PASS":
            raise ValueError("Privileged success after an unqualified boundary")


async def attempt(*, development_agent_prototype: bool = False) -> dict:
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
                with (
                    isolated_startup_store_b(),
                    configured_settings(
                        {
                            "database_url": database,
                            "auto_migrate": False,
                            "auth_enabled": True,
                            "api_keys": [],
                            "environment": "development",
                            "web_auth_dev_tokens": False,
                            "dev_agent_auth_enabled": development_agent_prototype,
                            "web_session_secure": False,
                            "web_verification_delivery_url": f"{mailbox}/deliver",
                            "web_verification_delivery_token": delivery_secret,
                        }
                    ),
                ):
                    async with serve(dashboard.app) as origin:
                        config = {
                            "origin": origin,
                            "phases": PHASES,
                            "developmentAgentPrototype": development_agent_prototype,
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
                                process.communicate(json.dumps(config).encode()),
                                420 if development_agent_prototype else 180,
                            )
                            if process.returncode:
                                raise RuntimeError("Browser failed; private diagnostics withheld")
                            result = json.loads(stdout)
                            validate_evidence(result)
                            result["implementation_git"] = git_identity(implementation)
                            result["harness_git"] = git_identity(root)
                            result["fresh_postgresql"] = True
                            result["migration_configuration"] = str(ini)
                            # Read-only diagnostics, never provision missing identity rows.
                            async with get_enterprise_engine().raw.connect() as connection:
                                user_id = await connection.scalar(
                                    select(web_users.c.id).where(
                                        web_users.c.email == config["credentials"]["email"]
                                    )
                                )
                                count = await connection.scalar(
                                    select(func.count())
                                    .select_from(trust_fabric_principals)
                                    .where(trust_fabric_principals.c.id == user_id)
                                )
                                result["identity_binding_diagnostic"] = {
                                    "user_exists": user_id is not None,
                                    "canonical_principal_count": count,
                                    "read_only": True,
                                }
                                for table, field in (
                                    (governance_root_authority_records, "root_records"),
                                    (governance_consent_proofs, "consent_records"),
                                ):
                                    result["identity_binding_diagnostic"][
                                        field
                                    ] = await connection.scalar(
                                        select(func.count())
                                        .select_from(table)
                                        .where(table.c.subject_id == user_id)
                                    )
                            return result
                        finally:
                            if process.returncode is None:
                                process.kill()
                                await process.wait()
    raise RuntimeError("Disposable PostgreSQL was not created")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--development-agent-prototype", action="store_true")
    args = parser.parse_args()
    try:
        evidence = asyncio.run(
            attempt(development_agent_prototype=args.development_agent_prototype)
        )
    except Exception as error:
        evidence = {"acceptance": "FAIL", "error_type": type(error).__name__}
    args.report.write_text(json.dumps(evidence, indent=2) + "\n")
    raise SystemExit(0 if evidence.get("acceptance") == "PASS" else 2)
