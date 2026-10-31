-- WhitePact M13 SEC-CF-007 — Authority boundary (NON-LIVE design)
-- NOT applied to any live Neon project by this agent.
--
-- Edge webhook role may record provider proofing evidence only.
-- IDENTITY_VERIFIED may be written ONLY by whitepact_sovereign (or superuser in lab).
-- Neon is NOT a second admission service / identity authority.

BEGIN;

-- Provider proofing + sovereign admission columns (additive).
ALTER TABLE identity_verifications
  ADD COLUMN IF NOT EXISTS provider_proofing_status TEXT,
  ADD COLUMN IF NOT EXISTS sovereign_admission TEXT NOT NULL DEFAULT 'PENDING';

-- Allowed sovereign statuses.
ALTER TABLE identity_verifications
  DROP CONSTRAINT IF EXISTS identity_verifications_status_chk;
ALTER TABLE identity_verifications
  ADD CONSTRAINT identity_verifications_status_chk
  CHECK (status IN (
    'REVIEW_REQUIRED',
    'IDENTITY_VERIFIED',
    'REJECTED',
    'SUSPENDED'
  ));

ALTER TABLE identity_verifications
  DROP CONSTRAINT IF EXISTS identity_verifications_proofing_chk;
ALTER TABLE identity_verifications
  ADD CONSTRAINT identity_verifications_proofing_chk
  CHECK (
    provider_proofing_status IS NULL OR provider_proofing_status IN (
      'PROVIDER_APPROVED',
      'PROVIDER_REJECTED',
      'PROVIDER_REVIEW',
      'PROVIDER_SUSPENDED'
    )
  );

ALTER TABLE identity_verifications
  DROP CONSTRAINT IF EXISTS identity_verifications_admission_chk;
ALTER TABLE identity_verifications
  ADD CONSTRAINT identity_verifications_admission_chk
  CHECK (sovereign_admission IN (
    'PENDING',
    'ADMITTED',
    'DENIED',
    'REVOCATION_PENDING'
  ));

-- Fail-closed: ADMITTED requires IDENTITY_VERIFIED; IDENTITY_VERIFIED requires ADMITTED.
ALTER TABLE identity_verifications
  DROP CONSTRAINT IF EXISTS identity_verifications_admit_consistent_chk;
ALTER TABLE identity_verifications
  ADD CONSTRAINT identity_verifications_admit_consistent_chk
  CHECK (
    (status = 'IDENTITY_VERIFIED' AND sovereign_admission = 'ADMITTED')
    OR (status <> 'IDENTITY_VERIFIED' AND sovereign_admission <> 'ADMITTED')
  );

-- Trigger: non-sovereign sessions cannot elevate to IDENTITY_VERIFIED.
CREATE OR REPLACE FUNCTION whitepact_prevent_edge_identity_elevation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.status = 'IDENTITY_VERIFIED'
     AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM 'IDENTITY_VERIFIED') THEN
    IF current_setting('whitepact.sovereign_admit', true) IS DISTINCT FROM 'on'
       AND current_user NOT IN ('whitepact_sovereign') THEN
      RAISE EXCEPTION 'SEC-CF-007: edge/non-sovereign role cannot grant IDENTITY_VERIFIED'
        USING ERRCODE = '42501';
    END IF;
  END IF;
  IF NEW.sovereign_admission = 'ADMITTED'
     AND (TG_OP = 'INSERT' OR OLD.sovereign_admission IS DISTINCT FROM 'ADMITTED') THEN
    IF current_setting('whitepact.sovereign_admit', true) IS DISTINCT FROM 'on'
       AND current_user NOT IN ('whitepact_sovereign') THEN
      RAISE EXCEPTION 'SEC-CF-007: edge/non-sovereign role cannot set sovereign_admission=ADMITTED'
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

-- Least-privilege edge role (lab / disposable). Does not own elevation.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'whitepact_edge_webhook') THEN
    CREATE ROLE whitepact_edge_webhook NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'whitepact_sovereign') THEN
    CREATE ROLE whitepact_sovereign NOLOGIN;
  END IF;
END $$;

-- Table privileges: edge can write evidence; cannot bypass trigger.
GRANT SELECT, INSERT, UPDATE, DELETE ON identity_session_bindings TO whitepact_edge_webhook;
GRANT SELECT, INSERT, UPDATE, DELETE ON identity_provider_events TO whitepact_edge_webhook;
GRANT SELECT, INSERT, UPDATE, DELETE ON identity_verifications TO whitepact_edge_webhook;
GRANT SELECT, INSERT, UPDATE, DELETE ON identity_reconciliation_deadletters TO whitepact_edge_webhook;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'identity_reconciliation_jobs') THEN
    EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON identity_reconciliation_jobs TO whitepact_edge_webhook';
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'identity_webhook_delivery_ops') THEN
    EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON identity_webhook_delivery_ops TO whitepact_edge_webhook';
  END IF;
END $$;

GRANT SELECT, INSERT, UPDATE, DELETE ON identity_verifications TO whitepact_sovereign;
GRANT SELECT ON identity_session_bindings TO whitepact_sovereign;
GRANT SELECT ON identity_provider_events TO whitepact_sovereign;

-- Fail-closed authority denial events (no PII payloads).
CREATE TABLE IF NOT EXISTS identity_authority_denials (
  id              TEXT PRIMARY KEY,
  provider        TEXT NOT NULL,
  session_id      TEXT,
  user_id         TEXT,
  org_id          TEXT,
  reason_code     TEXT NOT NULL,
  observed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

GRANT SELECT, INSERT ON identity_authority_denials TO whitepact_edge_webhook;
GRANT SELECT, INSERT ON identity_authority_denials TO whitepact_sovereign;

COMMIT;
