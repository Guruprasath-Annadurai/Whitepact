-- Copyright (c) 2026 Guruprasath Annadurai
-- SPDX-License-Identifier: MIT
-- Execution-tier login. The password is set out of band and must not equal
-- the authority owner password. Do not grant this role to the table owner.
-- Canonical authority and admission tables covered when they exist:
--   governance_policies
--   governance_policy_versions
--   governance_approvals
--   governance_approval_votes
--   governance_delegations
--   governance_root_authority_records
--   governance_authority_passports
--   governance_revocation_epochs
--   governance_consent_proofs
--   org_authority_ceilings
--   org_autonomy_budgets
--   governance_execution_authorizations
--   governance_execution_nonces

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'whitepact_authority') THEN
    CREATE ROLE whitepact_authority
      WITH NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;
  ELSE
    ALTER ROLE whitepact_authority
      WITH NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'whitepact_execution') THEN
    CREATE ROLE whitepact_execution
      WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;
  ELSE
    ALTER ROLE whitepact_execution
      WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;
  END IF;
END
$$;

GRANT whitepact_authority TO CURRENT_USER;

REVOKE CREATE ON SCHEMA public FROM whitepact_execution;
GRANT USAGE ON SCHEMA public TO whitepact_execution;

CREATE OR REPLACE FUNCTION whitepact_admit_execution(p_authorization_id text)
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

REVOKE ALL ON FUNCTION whitepact_admit_execution(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION whitepact_admit_execution(text) FROM whitepact_execution;
GRANT EXECUTE ON FUNCTION whitepact_admit_execution(text) TO whitepact_authority;

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM whitepact_execution;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM whitepact_execution;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM whitepact_execution;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM whitepact_execution;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM whitepact_execution;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM whitepact_execution;
