-- WhitePact M13 SEC-CF-007D — Guard admitted identity against edge demotion (NON-LIVE)
-- NOT applied to any live Neon project by this agent.
--
-- Defect: edge UPDATE on identity_verifications could change IDENTITY_VERIFIED / ADMITTED
-- into SUSPENDED/REJECTED (unauthorized lockout) without sovereign authority.
--
-- Policy:
--   * Provider revocation evidence → provider_proofing_status only (append-only events)
--   * Immediate fail-closed access → execution gate reads proofing hold (app layer)
--   * Sovereign admission-state mutation → whitepact_sovereign_login only

BEGIN;

CREATE OR REPLACE FUNCTION whitepact_prevent_edge_identity_elevation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  actor text := session_user;
BEGIN
  -- 007A: only sovereign_login may newly grant IDENTITY_VERIFIED / ADMITTED
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

  -- 007D: non-sovereign cannot mutate sovereign status/admission of an admitted identity
  IF TG_OP = 'UPDATE' AND actor IS DISTINCT FROM 'whitepact_sovereign_login' THEN
    IF OLD.status = 'IDENTITY_VERIFIED' AND NEW.status IS DISTINCT FROM OLD.status THEN
      RAISE EXCEPTION
        'SEC-CF-007D: edge/non-sovereign cannot change status of admitted identity (% → %)',
        OLD.status, NEW.status
        USING ERRCODE = '42501';
    END IF;
    IF OLD.sovereign_admission = 'ADMITTED'
       AND NEW.sovereign_admission IS DISTINCT FROM OLD.sovereign_admission THEN
      RAISE EXCEPTION
        'SEC-CF-007D: edge/non-sovereign cannot change ADMITTED admission state (% → %)',
        OLD.sovereign_admission, NEW.sovereign_admission
        USING ERRCODE = '42501';
    END IF;
    -- Binding integrity: never rebind subject/tenant on verification row
    IF NEW.user_id IS DISTINCT FROM OLD.user_id OR NEW.org_id IS DISTINCT FROM OLD.org_id THEN
      RAISE EXCEPTION 'SEC-CF-007D: edge cannot rebind user_id/org_id on verification'
        USING ERRCODE = '42501';
    END IF;
    IF NEW.provider IS DISTINCT FROM OLD.provider
       OR NEW.provider_reference_id IS DISTINCT FROM OLD.provider_reference_id THEN
      RAISE EXCEPTION 'SEC-CF-007D: edge cannot rebind provider reference'
        USING ERRCODE = '42501';
    END IF;
  END IF;

  RETURN NEW;
END;
$$;

ALTER FUNCTION whitepact_prevent_edge_identity_elevation() OWNER TO whitepact_migration_owner;

DROP TRIGGER IF EXISTS trg_prevent_edge_identity_elevation ON identity_verifications;
CREATE TRIGGER trg_prevent_edge_identity_elevation
  BEFORE INSERT OR UPDATE ON identity_verifications
  FOR EACH ROW
  EXECUTE PROCEDURE whitepact_prevent_edge_identity_elevation();

-- Narrow edge column updates: prefer proofing + timestamps; status still needed pre-admit.
-- Admitted rows are protected by trigger above even if UPDATE privilege remains.
REVOKE UPDATE ON identity_verifications FROM whitepact_edge_webhook, whitepact_edge_login;
GRANT UPDATE (
  status,
  provider_proofing_status,
  sovereign_admission,
  assurance_level,
  expires_at,
  updated_at
) ON identity_verifications TO whitepact_edge_webhook, whitepact_edge_login;
-- Explicitly no UPDATE on user_id/org_id/provider/provider_reference_id/verified_at/id

COMMENT ON FUNCTION whitepact_prevent_edge_identity_elevation() IS
  'SEC-CF-007A/D: session_user sovereign_login for elevation; block edge demotion of admitted identity';

COMMIT;
