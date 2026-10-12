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
    """SQL applied by the migrator after schema migrations. No password is embedded.

    Identifiers are literals. They are not assembled from request data.
    """
    sql = (
        "-- Copyright (c) 2026 Guruprasath Annadurai\n"
        "-- SPDX-License-Identifier: MIT\n"
        "-- Execution-tier login. The password is set out of band and must not equal\n"
        "-- the authority owner password. Do not grant this role to the table owner.\n"
        "-- Canonical authority and admission tables covered when they exist:\n"
        "--   governance_policies\n"
        "--   governance_policy_versions\n"
        "--   governance_approvals\n"
        "--   governance_approval_votes\n"
        "--   governance_delegations\n"
        "--   governance_root_authority_records\n"
        "--   governance_authority_passports\n"
        "--   governance_revocation_epochs\n"
        "--   governance_consent_proofs\n"
        "--   org_authority_ceilings\n"
        "--   org_autonomy_budgets\n"
        "--   governance_execution_authorizations\n"
        "--   governance_execution_nonces\n"
        "\n"
        "DO $$\n"
        "BEGIN\n"
        "  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'whitepact_authority') THEN\n"
        "    CREATE ROLE whitepact_authority\n"
        "      WITH NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;\n"
        "  ELSE\n"
        "    ALTER ROLE whitepact_authority\n"
        "      WITH NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;\n"
        "  END IF;\n"
        "  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'whitepact_execution') THEN\n"
        "    CREATE ROLE whitepact_execution\n"
        "      WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;\n"
        "  ELSE\n"
        "    ALTER ROLE whitepact_execution\n"
        "      WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;\n"
        "  END IF;\n"
        "END\n"
        "$$;\n"
        "\n"
        "GRANT whitepact_authority TO CURRENT_USER;\n"
        "\n"
        "REVOKE CREATE ON SCHEMA public FROM whitepact_execution;\n"
        "GRANT USAGE ON SCHEMA public TO whitepact_execution;\n"
        "\n"
        "CREATE OR REPLACE FUNCTION whitepact_admit_execution(p_authorization_id text)\n"
        "RETURNS void\n"
        "LANGUAGE plpgsql\n"
        "SECURITY DEFINER\n"
        "SET search_path = pg_catalog, public\n"
        "AS $$\n"
        "BEGIN\n"
        "  UPDATE public.governance_execution_authorizations\n"
        "     SET status = 'CONSUMED'\n"
        "   WHERE authorization_id = p_authorization_id\n"
        "     AND status = 'ISSUED';\n"
        "  IF NOT FOUND THEN\n"
        "    RAISE EXCEPTION 'admission refused';\n"
        "  END IF;\n"
        "END;\n"
        "$$;\n"
        "\n"
        "REVOKE ALL ON FUNCTION whitepact_admit_execution(text) FROM PUBLIC;\n"
        "REVOKE ALL ON FUNCTION whitepact_admit_execution(text) FROM whitepact_execution;\n"
        "GRANT EXECUTE ON FUNCTION whitepact_admit_execution(text) TO whitepact_authority;\n"
        "\n"
        "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM whitepact_execution;\n"
        "REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM whitepact_execution;\n"
        "REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM whitepact_execution;\n"
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE ALL ON TABLES FROM whitepact_execution;\n"
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE ALL ON SEQUENCES FROM whitepact_execution;\n"
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE ALL ON FUNCTIONS FROM whitepact_execution;\n"
    )
    for token in (EXECUTION_ROLE, AUTHORITY_ROLE, ADMIT_FUNCTION):
        if token not in sql:
            raise RuntimeError("execution role SQL drifted from its identifiers")
    return sql


def fixture_tables_sql() -> str:
    """Minimal tables for the hostile credential test. Not a schema migration."""
    return (
        "CREATE TABLE governance_policies (id text PRIMARY KEY, body text NOT NULL);\n"
        "CREATE TABLE governance_policy_versions (id text PRIMARY KEY, body text NOT NULL);\n"
        "CREATE TABLE governance_approvals (id text PRIMARY KEY, status text NOT NULL);\n"
        "CREATE TABLE governance_approval_votes (id text PRIMARY KEY, body text NOT NULL);\n"
        "CREATE TABLE governance_delegations (id text PRIMARY KEY, body text NOT NULL);\n"
        "CREATE TABLE governance_root_authority_records "
        "(id text PRIMARY KEY, body text NOT NULL);\n"
        "CREATE TABLE governance_authority_passports (id text PRIMARY KEY, body text NOT NULL);\n"
        "CREATE TABLE governance_revocation_epochs ("
        "organization_id text PRIMARY KEY, epoch integer NOT NULL);\n"
        "CREATE TABLE governance_consent_proofs (id text PRIMARY KEY, body text NOT NULL);\n"
        "CREATE TABLE org_authority_ceilings (id text PRIMARY KEY, body text NOT NULL);\n"
        "CREATE TABLE org_autonomy_budgets (id text PRIMARY KEY, body text NOT NULL);\n"
        "CREATE TABLE governance_execution_authorizations ("
        "authorization_id text PRIMARY KEY, status text NOT NULL);\n"
        "CREATE TABLE governance_execution_nonces ("
        "nonce text PRIMARY KEY, consumed boolean NOT NULL);\n"
    )


def hostile_statements() -> tuple[str, ...]:
    """Statements a compromised execution login must not be allowed to run.

    Table names are literals from the canonical list, not request data.
    """
    return (
        "INSERT INTO governance_policies DEFAULT VALUES",
        "DELETE FROM governance_policies",
        "SELECT * FROM governance_policies",
        "INSERT INTO governance_policy_versions DEFAULT VALUES",
        "DELETE FROM governance_policy_versions",
        "SELECT * FROM governance_policy_versions",
        "INSERT INTO governance_approvals DEFAULT VALUES",
        "DELETE FROM governance_approvals",
        "SELECT * FROM governance_approvals",
        "INSERT INTO governance_approval_votes DEFAULT VALUES",
        "DELETE FROM governance_approval_votes",
        "SELECT * FROM governance_approval_votes",
        "INSERT INTO governance_delegations DEFAULT VALUES",
        "DELETE FROM governance_delegations",
        "SELECT * FROM governance_delegations",
        "INSERT INTO governance_root_authority_records DEFAULT VALUES",
        "DELETE FROM governance_root_authority_records",
        "SELECT * FROM governance_root_authority_records",
        "INSERT INTO governance_authority_passports DEFAULT VALUES",
        "DELETE FROM governance_authority_passports",
        "SELECT * FROM governance_authority_passports",
        "INSERT INTO governance_revocation_epochs DEFAULT VALUES",
        "DELETE FROM governance_revocation_epochs",
        "SELECT * FROM governance_revocation_epochs",
        "INSERT INTO governance_consent_proofs DEFAULT VALUES",
        "DELETE FROM governance_consent_proofs",
        "SELECT * FROM governance_consent_proofs",
        "INSERT INTO org_authority_ceilings DEFAULT VALUES",
        "DELETE FROM org_authority_ceilings",
        "SELECT * FROM org_authority_ceilings",
        "INSERT INTO org_autonomy_budgets DEFAULT VALUES",
        "DELETE FROM org_autonomy_budgets",
        "SELECT * FROM org_autonomy_budgets",
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
