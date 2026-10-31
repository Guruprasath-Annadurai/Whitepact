-- WhitePact M13 — Neon Free durable identity-event schema (design + local review)
-- NOT applied to any live Neon project by this agent.
-- Privacy: no columns for raw documents, images, biometrics, or full decision blobs.

BEGIN;

CREATE TABLE IF NOT EXISTS identity_session_bindings (
  provider       TEXT NOT NULL,
  session_id     TEXT NOT NULL,
  user_id        TEXT NOT NULL,
  org_id         TEXT NOT NULL,
  context_hash   TEXT NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (provider, session_id)
);

-- Append-mostly provider event ledger. Unique (provider, event_id) = idempotency key.
CREATE TABLE IF NOT EXISTS identity_provider_events (
  id             TEXT PRIMARY KEY,
  provider       TEXT NOT NULL,
  event_id       TEXT NOT NULL,
  user_id        TEXT,
  org_id         TEXT,
  payload_hash   TEXT NOT NULL,
  session_id     TEXT,
  status         TEXT,
  webhook_type   TEXT,
  environment    TEXT,
  received_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT identity_provider_events_uniq UNIQUE (provider, event_id)
);

CREATE INDEX IF NOT EXISTS identity_provider_events_session_idx
  ON identity_provider_events (provider, session_id);

-- Outcome mirror without media. Assurance labels only; no document payloads.
CREATE TABLE IF NOT EXISTS identity_verifications (
  id                      TEXT PRIMARY KEY,
  provider                TEXT NOT NULL,
  provider_reference_id   TEXT NOT NULL,
  user_id                 TEXT NOT NULL,
  org_id                  TEXT NOT NULL,
  status                  TEXT NOT NULL,
  assurance_level         TEXT,
  verified_at             TIMESTAMPTZ,
  expires_at              TIMESTAMPTZ,
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT identity_verifications_session_uniq
    UNIQUE (provider, provider_reference_id)
);

-- Optional reconciliation queue when Neon was unavailable past Didit retries.
-- Operators drain this after store recovery; never auto-elevates identity.
CREATE TABLE IF NOT EXISTS identity_reconciliation_deadletters (
  id             TEXT PRIMARY KEY,
  provider       TEXT NOT NULL,
  event_id       TEXT,
  session_id     TEXT,
  reason         TEXT NOT NULL,
  payload_hash   TEXT,
  observed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at    TIMESTAMPTZ
);

COMMIT;
