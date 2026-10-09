# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Execution-tier database credentials cannot mutate authority or self-admit."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from responsibleai.ops.execution_db_boundary import (
    ADMISSION_TABLES,
    CANONICAL_AUTHORITY_TABLES,
    execution_role_sql,
    fixture_tables_sql,
    hostile_statements,
)

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "infra" / "postgres" / "whitepact_execution_role.sql"
PG_ENV = {
    "PGHOST": "127.0.0.1",
    "PGPORT": "55432",
    "PGUSER": "wp",
    "PGPASSWORD": "wp",
}
EXECUTION_PASSWORD = "execution-tier-test-only"


def test_execution_role_sql_matches_the_committed_contract() -> None:
    assert SQL_PATH.read_text(encoding="utf-8") == execution_role_sql()
    text = SQL_PATH.read_text(encoding="utf-8")
    for name in CANONICAL_AUTHORITY_TABLES + ADMISSION_TABLES:
        assert name in text
    assert "GRANT INSERT" not in text
    assert "GRANT UPDATE" not in text
    assert "GRANT DELETE" not in text
    assert "GRANT SELECT" not in text
    assert "NOSUPERUSER" in text
    assert "REVOKE ALL ON FUNCTION whitepact_admit_execution(text) FROM PUBLIC" in text
    assert (
        "GRANT EXECUTE ON FUNCTION whitepact_admit_execution(text) TO whitepact_authority" in text
    )
    assert "PASSWORD" not in text


def _psql(
    *args: str, user: str = "wp", password: str = "wp", database: str = "postgres"
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(PG_ENV)
    env["PGUSER"] = user
    env["PGPASSWORD"] = password
    env["PGDATABASE"] = database
    return subprocess.run(
        ["psql", "-v", "ON_ERROR_STOP=1", *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def _postgres_up() -> bool:
    result = _psql("-tAc", "SELECT 1")
    return result.returncode == 0 and result.stdout.strip() == "1"


def test_execution_login_cannot_mutate_authority_or_admit() -> None:
    if not _postgres_up():
        pytest.fail("isolated Postgres is not listening on 127.0.0.1:55432")
    suffix = os.urandom(4).hex()
    database = f"wp_exec_boundary_{suffix}"
    created = _psql("-c", f'CREATE DATABASE "{database}"')
    assert created.returncode == 0, created.stderr
    try:
        tables = _psql("-c", fixture_tables_sql(), database=database)
        assert tables.returncode == 0, tables.stderr
        applied = _psql("-f", str(SQL_PATH), database=database)
        assert applied.returncode == 0, applied.stderr
        password = _psql(
            "-c",
            f"ALTER ROLE whitepact_execution PASSWORD '{EXECUTION_PASSWORD}'",
            database=database,
        )
        assert password.returncode == 0, password.stderr
        seeded = _psql(
            "-c",
            "INSERT INTO governance_policies (id, body) VALUES ('policy-1', 'canonical'); "
            "INSERT INTO governance_execution_authorizations (authorization_id, status) "
            "VALUES ('auth-1', 'ISSUED'); "
            "INSERT INTO governance_revocation_epochs (organization_id, epoch) VALUES ('org-1', 7); "
            "INSERT INTO governance_approvals (id, status) VALUES ('approval-1', 'pending');",
            database=database,
        )
        assert seeded.returncode == 0, seeded.stderr
        admitted = _psql(
            "-c",
            "SELECT whitepact_admit_execution('auth-1');",
            database=database,
        )
        assert admitted.returncode == 0, admitted.stderr
        consumed = _psql(
            "-tAc",
            "SELECT status FROM governance_execution_authorizations WHERE authorization_id = 'auth-1'",
            database=database,
        )
        assert consumed.stdout.strip() == "CONSUMED"

        for statement in hostile_statements():
            denied = _psql(
                "-c",
                statement,
                user="whitepact_execution",
                password=EXECUTION_PASSWORD,
                database=database,
            )
            assert denied.returncode != 0, statement
            combined = (denied.stderr + denied.stdout).casefold()
            assert EXECUTION_PASSWORD not in combined
            assert "permission denied" in combined or "must be superuser" in combined, (
                statement,
                denied.stderr,
            )

        unchanged = _psql(
            "-tAc",
            "SELECT body FROM governance_policies WHERE id = 'policy-1'",
            database=database,
        )
        assert unchanged.stdout.strip() == "canonical"
        forged = _psql(
            "-tAc",
            "SELECT count(*) FROM governance_execution_authorizations WHERE authorization_id = 'forged'",
            database=database,
        )
        assert forged.stdout.strip() == "0"
        epoch = _psql(
            "-tAc",
            "SELECT epoch FROM governance_revocation_epochs WHERE organization_id = 'org-1'",
            database=database,
        )
        assert epoch.stdout.strip() == "7"
    finally:
        _psql("-c", f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE);')
