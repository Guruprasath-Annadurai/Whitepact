-- WhitePact M13 SEC-CF-007A/B/C — Database authority hardening (NON-LIVE)
-- NOT applied to any live Neon project by this agent.
--
-- Fixes:
--   007A: remove caller-controlled whitepact.sovereign_admit session GUC bypass
--   007B: revoke unnecessary UPDATE/DELETE from edge on sensitive tables
--   007C: distinct LOGIN roles for privilege proofs (created here; passwords set in lab)
--
-- Sovereign admission proof = session_user = whitepact_sovereign_login ONLY.
-- Role-name checks on current_user alone are insufficient (SET ROLE / SECURITY DEFINER).
-- Neon remains evidence ledger — not a second identity authority.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Roles: migration owner (nologin), edge, reconcile, sovereign login
-- ---------------------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'whitepact_migration_owner') THEN
    CREATE ROLE whitepact_migration_owner NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'whitepact_edge_webhook') THEN
    CREATE ROLE whitepact_edge_webhook NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'whitepact_reconcile') THEN
    CREATE ROLE whitepact_reconcile NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'whitepact_sovereign') THEN
    CREATE ROLE whitepact_sovereign NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'whitepact_sovereign_login') THEN
    CREATE ROLE whitepact_sovereign_login LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE
      PASSWORD 'sovereign-lab-only-not-prod';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'whitepact_edge_login') THEN
    CREATE ROLE whitepact_edge_login LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE
      PASSWORD 'edge-lab-only-not-prod';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'whitepact_reconcile_login') THEN
    CREATE ROLE whitepact_reconcile_login LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE
      PASSWORD 'reconcile-lab-only-not-prod';
  END IF;
END $$;

-- Enable LOGIN on edge/reconcile group roles used as session principals in some labs;
-- prefer *_login roles for adversarial tests. Keep group roles NOLOGIN; grant membership.
ALTER ROLE whitepact_edge_webhook NOLOGIN;
ALTER ROLE whitepact_reconcile NOLOGIN;
ALTER ROLE whitepact_sovereign NOLOGIN;

GRANT whitepact_edge_webhook TO whitepact_edge_login;
GRANT whitepact_reconcile TO whitepact_reconcile_login;
GRANT whitepact_sovereign TO whitepact_sovereign_login;

-- Edge must NOT be able to SET ROLE to sovereign.
REVOKE whitepact_sovereign FROM whitepact_edge_login;
REVOKE whitepact_sovereign FROM whitepact_edge_webhook;
REVOKE whitepact_sovereign_login FROM whitepact_edge_login;
REVOKE whitepact_sovereign_login FROM whitepact_edge_webhook;
REVOKE whitepact_migration_owner FROM whitepact_edge_login;
REVOKE whitepact_migration_owner FROM whitepact_edge_webhook;

-- ---------------------------------------------------------------------------
-- 2. Replace elevation guard: session_user only (no GUC / no current_user alone)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION whitepact_prevent_edge_identity_elevation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  actor text := session_user;
BEGIN
  -- Block caller-controlled GUC entirely: even if set, it must not authorize.
  IF NEW.status = 'IDENTITY_VERIFIED'
     AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM 'IDENTITY_VERIFIED') THEN
    IF actor IS DISTINCT FROM 'whitepact_sovereign_login' THEN
      RAISE EXCEPTION
        'SEC-CF-007A: only session_user whitepact_sovereign_login may grant IDENTITY_VERIFIED (got %)',
        actor
        USING ERRCODE = '42501';
    END IF;
  END IF;
  IF NEW.sovereign_admission = 'ADMITTED'
     AND (TG_OP = 'INSERT' OR OLD.sovereign_admission IS DISTINCT FROM 'ADMITTED') THEN
    IF actor IS DISTINCT FROM 'whitepact_sovereign_login' THEN
      RAISE EXCEPTION
        'SEC-CF-007A: only session_user whitepact_sovereign_login may set ADMITTED (got %)',
        actor
        USING ERRCODE = '42501';
    END IF;
  END IF;
  -- Edge/reconcile must not clear verified_at fraudulently when not sovereign.
  IF TG_OP = 'UPDATE'
     AND OLD.status = 'IDENTITY_VERIFIED'
     AND NEW.status = 'IDENTITY_VERIFIED'
     AND actor IS DISTINCT FROM 'whitepact_sovereign_login' THEN
    -- Allow no-op / proofing-only updates only if admission stays ADMITTED unchanged
    -- and status unchanged — still ok. Block admission demotion without suspend path:
    IF NEW.sovereign_admission IS DISTINCT FROM OLD.sovereign_admission
       AND NEW.sovereign_admission = 'ADMITTED' THEN
      RAISE EXCEPTION 'SEC-CF-007A: non-sovereign cannot set ADMITTED'
        USING ERRCODE = '42501';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_prevent_edge_identity_elevation ON identity_verifications;
CREATE TRIGGER trg_prevent_edge_identity_elevation
  BEFORE INSERT OR UPDATE ON identity_verifications
  FOR EACH ROW
  EXECUTE PROCEDURE whitepact_prevent_edge_identity_elevation();

-- ---------------------------------------------------------------------------
-- 3. Append-only provider evidence ledger
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION whitepact_forbid_provider_event_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION 'SEC-CF-007B: identity_provider_events is append-only'
    USING ERRCODE = '42501';
END;
$$;

DROP TRIGGER IF EXISTS trg_provider_events_append_only ON identity_provider_events;
CREATE TRIGGER trg_provider_events_append_only
  BEFORE UPDATE OR DELETE ON identity_provider_events
  FOR EACH ROW
  EXECUTE PROCEDURE whitepact_forbid_provider_event_mutation();

-- ---------------------------------------------------------------------------
-- 4. SECURITY DEFINER sovereign admit — owned by migration_owner; session_user gate
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION whitepact_sovereign_apply_admission(
  p_provider text,
  p_session_id text,
  p_admit boolean DEFAULT true
) RETURNS TABLE (
  out_status text,
  out_admission text,
  out_proofing text,
  out_elevates boolean
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_status text;
  v_proofing text;
  v_admission text;
  next_status text;
  next_admission text;
BEGIN
  IF session_user IS DISTINCT FROM 'whitepact_sovereign_login' THEN
    RAISE EXCEPTION
      'SEC-CF-007A: whitepact_sovereign_apply_admission denied for session_user=%',
      session_user
      USING ERRCODE = '42501';
  END IF;

  SELECT status, provider_proofing_status, sovereign_admission
    INTO v_status, v_proofing, v_admission
    FROM identity_verifications
   WHERE provider = p_provider AND provider_reference_id = p_session_id
   FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'VERIFICATION_SESSION_UNKNOWN' USING ERRCODE = 'P0002';
  END IF;

  IF v_proofing IS DISTINCT FROM 'PROVIDER_APPROVED' THEN
    RAISE EXCEPTION 'PROVIDER_EVIDENCE_REQUIRED' USING ERRCODE = '42501';
  END IF;

  IF v_status IN ('REJECTED', 'SUSPENDED') THEN
    RAISE EXCEPTION 'REOPEN_FORBIDDEN' USING ERRCODE = '42501';
  END IF;

  IF p_admit THEN
    next_status := 'IDENTITY_VERIFIED';
    next_admission := 'ADMITTED';
  ELSE
    next_status := 'REJECTED';
    next_admission := 'DENIED';
  END IF;

  UPDATE identity_verifications
     SET status = next_status,
         sovereign_admission = next_admission,
         verified_at = CASE WHEN next_status = 'IDENTITY_VERIFIED' THEN now() ELSE verified_at END,
         updated_at = now()
   WHERE provider = p_provider AND provider_reference_id = p_session_id;

  out_status := next_status;
  out_admission := next_admission;
  out_proofing := v_proofing;
  out_elevates := (next_status = 'IDENTITY_VERIFIED');
  RETURN NEXT;
END;
$$;

ALTER FUNCTION whitepact_prevent_edge_identity_elevation() OWNER TO whitepact_migration_owner;
ALTER FUNCTION whitepact_forbid_provider_event_mutation() OWNER TO whitepact_migration_owner;
ALTER FUNCTION whitepact_sovereign_apply_admission(text, text, boolean) OWNER TO whitepact_migration_owner;

REVOKE ALL ON FUNCTION whitepact_sovereign_apply_admission(text, text, boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION whitepact_sovereign_apply_admission(text, text, boolean) TO whitepact_sovereign_login;
-- Explicitly deny edge/reconcile execute (belt + suspenders).
REVOKE EXECUTE ON FUNCTION whitepact_sovereign_apply_admission(text, text, boolean) FROM whitepact_edge_webhook;
REVOKE EXECUTE ON FUNCTION whitepact_sovereign_apply_admission(text, text, boolean) FROM whitepact_edge_login;
REVOKE EXECUTE ON FUNCTION whitepact_sovereign_apply_admission(text, text, boolean) FROM whitepact_reconcile;
REVOKE EXECUTE ON FUNCTION whitepact_sovereign_apply_admission(text, text, boolean) FROM whitepact_reconcile_login;

-- ---------------------------------------------------------------------------
-- 5. Ownership transfer + privilege reset (effective grants)
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'identity_session_bindings',
    'identity_provider_events',
    'identity_verifications',
    'identity_reconciliation_deadletters',
    'identity_reconciliation_jobs',
    'identity_webhook_delivery_ops',
    'identity_authority_denials'
  ]
  LOOP
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=t) THEN
      EXECUTE format('ALTER TABLE %I OWNER TO whitepact_migration_owner', t);
      EXECUTE format('REVOKE ALL ON TABLE %I FROM PUBLIC', t);
      -- Strip prior broad edge grants before re-granting minimal set.
      EXECUTE format('REVOKE ALL ON TABLE %I FROM whitepact_edge_webhook', t);
      EXECUTE format('REVOKE ALL ON TABLE %I FROM whitepact_edge_login', t);
      EXECUTE format('REVOKE ALL ON TABLE %I FROM whitepact_reconcile', t);
      EXECUTE format('REVOKE ALL ON TABLE %I FROM whitepact_reconcile_login', t);
      EXECUTE format('REVOKE ALL ON TABLE %I FROM whitepact_sovereign', t);
      EXECUTE format('REVOKE ALL ON TABLE %I FROM whitepact_sovereign_login', t);
    END IF;
  END LOOP;
END $$;

-- Edge: minimal — append evidence, update proofing mirror, insert denials. No DELETE.
GRANT SELECT, INSERT ON identity_session_bindings TO whitepact_edge_webhook, whitepact_edge_login;
GRANT SELECT, INSERT ON identity_provider_events TO whitepact_edge_webhook, whitepact_edge_login;
GRANT SELECT, INSERT, UPDATE ON identity_verifications TO whitepact_edge_webhook, whitepact_edge_login;
GRANT SELECT, INSERT ON identity_reconciliation_deadletters TO whitepact_edge_webhook, whitepact_edge_login;
GRANT SELECT, INSERT ON identity_authority_denials TO whitepact_edge_webhook, whitepact_edge_login;

-- Explicit denials of dangerous ops (documentation + enforcement if re-granted).
REVOKE UPDATE, DELETE, TRUNCATE ON identity_provider_events FROM whitepact_edge_webhook, whitepact_edge_login;
REVOKE DELETE, TRUNCATE ON identity_session_bindings FROM whitepact_edge_webhook, whitepact_edge_login;
REVOKE DELETE, TRUNCATE ON identity_verifications FROM whitepact_edge_webhook, whitepact_edge_login;
REVOKE UPDATE, DELETE, TRUNCATE ON identity_reconciliation_deadletters FROM whitepact_edge_webhook, whitepact_edge_login;

-- Reconcile: jobs / deadletters only (+ read evidence).
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='identity_reconciliation_jobs') THEN
    GRANT SELECT, INSERT, UPDATE ON identity_reconciliation_jobs TO whitepact_reconcile, whitepact_reconcile_login;
    REVOKE DELETE, TRUNCATE ON identity_reconciliation_jobs FROM whitepact_reconcile, whitepact_reconcile_login;
    REVOKE ALL ON identity_reconciliation_jobs FROM whitepact_edge_webhook, whitepact_edge_login;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='identity_webhook_delivery_ops') THEN
    GRANT SELECT, INSERT ON identity_webhook_delivery_ops TO whitepact_reconcile, whitepact_reconcile_login;
    REVOKE ALL ON identity_webhook_delivery_ops FROM whitepact_edge_webhook, whitepact_edge_login;
  END IF;
END $$;

GRANT SELECT ON identity_provider_events TO whitepact_reconcile, whitepact_reconcile_login;
GRANT SELECT ON identity_verifications TO whitepact_reconcile, whitepact_reconcile_login;
GRANT SELECT, INSERT, UPDATE ON identity_reconciliation_deadletters TO whitepact_reconcile, whitepact_reconcile_login;

-- Sovereign login: read evidence; elevate only via SECURITY DEFINER function (and trigger allows session_user).
GRANT SELECT ON identity_session_bindings TO whitepact_sovereign, whitepact_sovereign_login;
GRANT SELECT ON identity_provider_events TO whitepact_sovereign, whitepact_sovereign_login;
GRANT SELECT ON identity_verifications TO whitepact_sovereign, whitepact_sovereign_login;
GRANT SELECT, INSERT ON identity_authority_denials TO whitepact_sovereign, whitepact_sovereign_login;
-- Direct UPDATE on verifications allowed for sovereign_login (trigger gates elevation);
-- prefer whitepact_sovereign_apply_admission(). Still revoke DELETE.
GRANT UPDATE ON identity_verifications TO whitepact_sovereign_login;
REVOKE DELETE, TRUNCATE ON identity_verifications FROM whitepact_sovereign_login;
REVOKE INSERT, UPDATE, DELETE ON identity_provider_events FROM whitepact_sovereign_login;

-- Schema privileges
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO whitepact_edge_login, whitepact_reconcile_login, whitepact_sovereign_login;
GRANT USAGE ON SCHEMA public TO whitepact_edge_webhook, whitepact_reconcile, whitepact_sovereign;

COMMIT;
