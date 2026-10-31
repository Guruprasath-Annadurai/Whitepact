-- WhitePact M13 — durable Didit reconciliation jobs (NON-LIVE design)
-- NOT applied to any live Neon project by this agent.
--
-- This table is a JOB / OBSERVATION ledger only.
-- It is NOT a second identity authority. Identity elevation remains exclusively
-- via signed webhook admission into identity_provider_events + identity_verifications.
-- Never store raw decision feature arrays, documents, biometrics, or national IDs.

BEGIN;

CREATE TABLE IF NOT EXISTS identity_reconciliation_jobs (
  id                 TEXT PRIMARY KEY,
  provider           TEXT NOT NULL,
  session_id         TEXT NOT NULL,
  user_id            TEXT NOT NULL,
  org_id             TEXT NOT NULL,
  reason             TEXT NOT NULL,
  state              TEXT NOT NULL,
  -- pending | scheduled | fetching | validated | applied | retryable_failure | terminal_manual
  attempt_count      INTEGER NOT NULL DEFAULT 0,
  last_error_class   TEXT,
  provider_status    TEXT,          -- Didit session status string only (e.g. Approved)
  decision_hash      TEXT,          -- sha256 of safe observation fields
  workflow_id        TEXT,
  application_id     TEXT,
  environment        TEXT,
  required_action    TEXT NOT NULL DEFAULT 'Obtain or resend the authentic signed provider event.',
  identity_transition BOOLEAN NOT NULL DEFAULT FALSE,
  elevates           BOOLEAN NOT NULL DEFAULT FALSE,
  next_attempt_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT identity_reconciliation_jobs_no_elevate
    CHECK (identity_transition = FALSE AND elevates = FALSE)
);

CREATE INDEX IF NOT EXISTS identity_reconciliation_jobs_open_idx
  ON identity_reconciliation_jobs (provider, session_id, state);

CREATE INDEX IF NOT EXISTS identity_reconciliation_jobs_schedule_idx
  ON identity_reconciliation_jobs (state, next_attempt_at);

-- Optional audit of delivery inspection / resend attempts (management API).
-- Entitlement to these Didit APIs is account-specific — do not assume access.
CREATE TABLE IF NOT EXISTS identity_webhook_delivery_ops (
  id                 TEXT PRIMARY KEY,
  provider           TEXT NOT NULL,
  destination_uuid   TEXT NOT NULL,
  delivery_uuid      TEXT,
  operation          TEXT NOT NULL, -- list | resend
  http_status        INTEGER,
  observed_at        TIMESTAMPTZ NOT NULL DEFAULT now()
  -- no request_body / media columns
);

COMMIT;
