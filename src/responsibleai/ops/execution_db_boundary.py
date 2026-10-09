# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Least privilege for the execution-tier database login.

The execution subnet may open TCP 5432 to the authority database. That path is
admission, not ownership. Role whitepact_execution must not mutate canonical
authority and must not call or replace the admission function.
"""

from __future__ import annotations

EXECUTION_ROLE = "whitepact_execution"
AUTHORITY_ROLE = "whitepact_authority"
ADMIT_FUNCTION = "whitepact_admit_execution"

CANONICAL_AUTHORITY_TABLES: tuple[str, ...] = (
    "governance_policies",
    "governance_policy_versions",
    "governance_approvals",
    "governance_approval_votes",
    "governance_delegations",
    "governance_root_authority_records",
    "governance_authority_passports",
    "governance_revocation_epochs",
    "governance_consent_proofs",
    "org_authority_ceilings",
    "org_autonomy_budgets",
)

ADMISSION_TABLES: tuple[str, ...] = (
    "governance_execution_authorizations",
    "governance_execution_nonces",
)


def execution_role_sql() -> str:
    """SQL applied by the migrator after schema migrations. No password is embedded."""
    covered = "\n".join(f"--   {name}" for name in CANONICAL_AUTHORITY_TABLES + ADMISSION_TABLES)
    return f"""-- Copyright (c) 2026 Guruprasath Annadurai
-- SPDX-License-Identifier: MIT
-- Execution-tier login. The password is set out of band and must not equal
-- the authority owner password. Do not grant this role to the table owner.
-- Canonical authority and admission tables covered when they exist:
{covered}

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{AUTHORITY_ROLE}') THEN
    CREATE ROLE {AUTHORITY_ROLE}
      WITH NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;
  ELSE
    ALTER ROLE {AUTHORITY_ROLE}
      WITH NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{EXECUTION_ROLE}') THEN
    CREATE ROLE {EXECUTION_ROLE}
      WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;
  ELSE
    ALTER ROLE {EXECUTION_ROLE}
      WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;
  END IF;
END
$$;

GRANT {AUTHORITY_ROLE} TO CURRENT_USER;

REVOKE CREATE ON SCHEMA public FROM {EXECUTION_ROLE};
GRANT USAGE ON SCHEMA public TO {EXECUTION_ROLE};

CREATE OR REPLACE FUNCTION {ADMIT_FUNCTION}(p_authorization_id text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
  UPDATE public.governance_execution_authorizations
     SET status = 'CONSUMED'
   WHERE authorization_id = p_authorization_id
     AND status = 'ISSUED';
  IF NOT FOUND THEN
    RAISE EXCEPTION 'admission refused';
  END IF;
END;
$$;

REVOKE ALL ON FUNCTION {ADMIT_FUNCTION}(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION {ADMIT_FUNCTION}(text) FROM {EXECUTION_ROLE};
GRANT EXECUTE ON FUNCTION {ADMIT_FUNCTION}(text) TO {AUTHORITY_ROLE};

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {EXECUTION_ROLE};
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {EXECUTION_ROLE};
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM {EXECUTION_ROLE};
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {EXECUTION_ROLE};
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {EXECUTION_ROLE};
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM {EXECUTION_ROLE};
"""


def fixture_tables_sql() -> str:
    """Minimal tables for the hostile credential test. Not a schema migration."""
    statements: list[str] = []
    for name in CANONICAL_AUTHORITY_TABLES:
        if name == "governance_revocation_epochs":
            statements.append(
                "CREATE TABLE governance_revocation_epochs ("
                "organization_id text PRIMARY KEY, epoch integer NOT NULL)"
            )
        elif name == "governance_approvals":
            statements.append(
                "CREATE TABLE governance_approvals (id text PRIMARY KEY, status text NOT NULL)"
            )
        else:
            statements.append(f"CREATE TABLE {name} (id text PRIMARY KEY, body text NOT NULL)")
    statements.append(
        "CREATE TABLE governance_execution_authorizations ("
        "authorization_id text PRIMARY KEY, status text NOT NULL)"
    )
    statements.append(
        "CREATE TABLE governance_execution_nonces ("
        "nonce text PRIMARY KEY, consumed boolean NOT NULL)"
    )
    return ";\n".join(statements) + ";\n"


def hostile_statements() -> tuple[str, ...]:
    """Statements a compromised execution login must not be allowed to run."""
    denied: list[str] = []
    for name in CANONICAL_AUTHORITY_TABLES:
        denied.append(f"INSERT INTO {name} DEFAULT VALUES")
        denied.append(f"DELETE FROM {name}")
        denied.append(f"SELECT * FROM {name}")
    denied.extend(
        (
            "UPDATE governance_policies SET body = 'mutated'",
            "UPDATE governance_approvals SET status = 'approved'",
            "UPDATE governance_revocation_epochs SET epoch = 0",
            "INSERT INTO governance_execution_authorizations "
            "(authorization_id, status) VALUES ('forged', 'ISSUED')",
            "UPDATE governance_execution_authorizations SET status = 'ISSUED'",
            "DELETE FROM governance_execution_authorizations",
            "SELECT * FROM governance_execution_authorizations",
            "INSERT INTO governance_execution_nonces (nonce, consumed) VALUES ('replay', false)",
            "DELETE FROM governance_execution_nonces",
            "SELECT whitepact_admit_execution('forged')",
            "SET ROLE whitepact_authority",
            "ALTER ROLE whitepact_execution WITH SUPERUSER",
            "CREATE TABLE whitepact_execution_bypass (id integer)",
        )
    )
    return tuple(denied)
