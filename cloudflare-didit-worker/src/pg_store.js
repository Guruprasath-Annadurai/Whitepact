/**
 * Real PostgreSQL durable store (disposable local / future Neon).
 * Uses explicit BEGIN / FOR UPDATE / COMMIT / ROLLBACK.
 *
 * SEC-CF-007: edge commits provider proofing only — never IDENTITY_VERIFIED.
 * Sovereign admission uses set_config('whitepact.sovereign_admit','on',true).
 */

import { randomUUID } from "node:crypto";
import pg from "pg";
import { payloadHashHex } from "./verify.js";
import { assertNoMediaInRecord, durableProjection } from "./redact.js";
import {
  applyEdgeProviderOutcome,
  mapDiditStatusToProviderProofing,
  SOVEREIGN_ADMISSION,
  SOVEREIGN_STATUS,
} from "./authority_status.js";
import {
  OutOfOrderError,
  ReplayConflictError,
  SessionUnknownError,
  StoreUnavailableError,
  TenantIsolationError,
} from "./store.js";

export class PgIdentityStore {
  constructor(pool, { provider = "didit-sandbox", suspended = false } = {}) {
    this.pool = pool;
    this.provider = provider;
    this.suspended = suspended;
    this.committedAcks = [];
  }

  simulateSuspension(on = true) {
    this.suspended = on;
  }

  _gate() {
    if (this.suspended) {
      throw new StoreUnavailableError("PostgreSQL compute suspended.", "suspended");
    }
  }

  async bindSession({ sessionId, userId, orgId, contextHash }) {
    this._gate();
    const client = await this.pool.connect();
    try {
      await client.query("BEGIN");
      await client.query(
        `INSERT INTO identity_session_bindings
           (provider, session_id, user_id, org_id, context_hash)
         VALUES ($1,$2,$3,$4,$5)
         ON CONFLICT (provider, session_id) DO NOTHING`,
        [this.provider, sessionId, userId, orgId, contextHash],
      );
      await client.query(
        `INSERT INTO identity_verifications
           (id, provider, provider_reference_id, user_id, org_id, status,
            provider_proofing_status, sovereign_admission)
         VALUES ($1,$2,$3,$4,$5,'REVIEW_REQUIRED', NULL, 'PENDING')
         ON CONFLICT (provider, provider_reference_id) DO NOTHING`,
        [randomUUID(), this.provider, sessionId, userId, orgId],
      );
      await client.query("COMMIT");
      return { duplicate: false };
    } catch (err) {
      await client.query("ROLLBACK");
      throw new StoreUnavailableError(err.message, "connection_failure");
    } finally {
      client.release();
    }
  }

  async commitIdentityEvent(event, { testDelivery = false, abortAfterInsert = false } = {}) {
    this._gate();
    const projection = durableProjection(event);
    assertNoMediaInRecord(projection);
    const digest = payloadHashHex(event);
    const eventKey = (testDelivery ? "test:" : "event:") + event.event_id;

    const client = await this.pool.connect();
    try {
      await client.query("BEGIN");
      // Explicitly clear sovereign gate for edge path.
      await client.query("SELECT set_config('whitepact.sovereign_admit', 'off', true)");

      if (testDelivery) {
        const prior = await client.query(
          `SELECT payload_hash FROM identity_provider_events
           WHERE provider=$1 AND event_id=$2 FOR UPDATE`,
          [this.provider, eventKey],
        );
        if (prior.rowCount) {
          if (prior.rows[0].payload_hash !== digest) throw new ReplayConflictError();
          await client.query("COMMIT");
          return {
            status: "TEST_RECEIPT_ONLY",
            duplicate: true,
            identity_transition: false,
            elevates: false,
            execution_granted: false,
          };
        }
        await client.query(
          `INSERT INTO identity_provider_events
             (id, provider, event_id, payload_hash, session_id, status, webhook_type, environment)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8)`,
          [
            randomUUID(),
            this.provider,
            eventKey,
            digest,
            event.session_id,
            event.status,
            event.webhook_type,
            event.environment,
          ],
        );
        await client.query("COMMIT");
        this.committedAcks.push(eventKey);
        return {
          status: "TEST_RECEIPT_ONLY",
          duplicate: false,
          identity_transition: false,
          elevates: false,
          execution_granted: false,
        };
      }

      const binding = await client.query(
        `SELECT user_id, org_id, context_hash FROM identity_session_bindings
         WHERE provider=$1 AND session_id=$2 FOR UPDATE`,
        [this.provider, event.session_id],
      );
      if (!binding.rowCount) throw new SessionUnknownError();
      if (binding.rows[0].user_id !== event.vendor_data) throw new TenantIsolationError();

      const prior = await client.query(
        `SELECT payload_hash FROM identity_provider_events
         WHERE provider=$1 AND event_id=$2 FOR UPDATE`,
        [this.provider, eventKey],
      );
      if (prior.rowCount) {
        if (prior.rows[0].payload_hash !== digest) throw new ReplayConflictError();
        await client.query("COMMIT");
        return {
          status: "ALREADY_PROCESSED",
          duplicate: true,
          identity_transition: false,
          elevates: false,
          execution_granted: false,
        };
      }

      const latestRes = await client.query(
        `SELECT event_id FROM identity_provider_events
         WHERE provider=$1 AND event_id LIKE $2`,
        [this.provider, event.session_id + ":%"],
      );
      let latest = -1;
      for (const row of latestRes.rows) {
        const parts = row.event_id.split(":");
        const ts = Number(parts[1]);
        if (Number.isFinite(ts) && ts > latest) latest = ts;
      }
      if (event.created_at <= latest) throw new OutOfOrderError();

      const proofing = mapDiditStatusToProviderProofing(event.status);
      if (!proofing) throw new TenantIsolationError("unsupported status");

      const ver = await client.query(
        `SELECT id, status, provider_proofing_status, sovereign_admission
           FROM identity_verifications
          WHERE provider=$1 AND provider_reference_id=$2 FOR UPDATE`,
        [this.provider, event.session_id],
      );
      if (!ver.rowCount) throw new SessionUnknownError();

      await client.query(
        `INSERT INTO identity_provider_events
           (id, provider, event_id, user_id, org_id, payload_hash,
            session_id, status, webhook_type, environment)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)`,
        [
          randomUUID(),
          this.provider,
          eventKey,
          binding.rows[0].user_id,
          binding.rows[0].org_id,
          digest,
          event.session_id,
          event.status,
          event.webhook_type,
          event.environment,
        ],
      );
      const orderKey = `${event.session_id}:${event.created_at}:${event.event_id}`;
      await client.query(
        `INSERT INTO identity_provider_events
           (id, provider, event_id, user_id, org_id, payload_hash, session_id, status)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8)`,
        [
          randomUUID(),
          this.provider,
          orderKey,
          binding.rows[0].user_id,
          binding.rows[0].org_id,
          digest,
          event.session_id,
          event.status,
        ],
      );

      if (abortAfterInsert) {
        throw new StoreUnavailableError("Forced abort after insert.", "txn_abort");
      }

      const prev = ver.rows[0];
      const edgeResult = applyEdgeProviderOutcome({
        currentSovereignStatus: prev.status,
        currentAdmission: prev.sovereign_admission,
        providerProofing: proofing,
      });
      if (
        edgeResult.status === SOVEREIGN_STATUS.IDENTITY_VERIFIED &&
        prev.status !== SOVEREIGN_STATUS.IDENTITY_VERIFIED
      ) {
        throw new StoreUnavailableError(
          "SEC-CF-007 invariant: edge attempted elevation.",
          "authority_boundary",
        );
      }

      await client.query(
        `UPDATE identity_verifications
         SET status=$3,
             provider_proofing_status=$4,
             sovereign_admission=$5,
             updated_at = now()
         WHERE provider=$1 AND provider_reference_id=$2`,
        [
          this.provider,
          event.session_id,
          edgeResult.status,
          edgeResult.provider_proofing_status,
          edgeResult.sovereign_admission,
        ],
      );

      await client.query("COMMIT");
      this.committedAcks.push(eventKey);
      return {
        status: edgeResult.provider_proofing_status,
        provider_proofing_status: edgeResult.provider_proofing_status,
        sovereign_status: edgeResult.status,
        sovereign_admission: edgeResult.sovereign_admission,
        sovereign_admission_required: edgeResult.sovereign_admission_required !== false,
        duplicate: false,
        identity_transition: false,
        elevates: false,
        execution_granted: false,
      };
    } catch (err) {
      try {
        await client.query("ROLLBACK");
      } catch {
        /* ignore */
      }
      if (
        err instanceof ReplayConflictError ||
        err instanceof TenantIsolationError ||
        err instanceof SessionUnknownError ||
        err instanceof OutOfOrderError ||
        err instanceof StoreUnavailableError
      ) {
        throw err;
      }
      if (err && err.code === "23505") {
        throw new StoreUnavailableError("Unique race; retry.", "unique_race");
      }
      // SEC-CF-007 trigger / privilege denial
      if (err && (err.code === "42501" || /SEC-CF-007/.test(err.message || ""))) {
        throw new StoreUnavailableError(err.message, "authority_boundary");
      }
      throw new StoreUnavailableError(err.message || "pg error", "connection_failure");
    } finally {
      client.release();
    }
  }

  async getVerificationStatus(sessionId) {
    const res = await this.pool.query(
      `SELECT status FROM identity_verifications
       WHERE provider=$1 AND provider_reference_id=$2`,
      [this.provider, sessionId],
    );
    return res.rows[0]?.status ?? null;
  }

  async getVerificationRow(sessionId) {
    const res = await this.pool.query(
      `SELECT status, provider_proofing_status, sovereign_admission, user_id, org_id
         FROM identity_verifications
        WHERE provider=$1 AND provider_reference_id=$2`,
      [this.provider, sessionId],
    );
    return res.rows[0] ?? null;
  }

  async countEvents(prefix = "event:") {
    const res = await this.pool.query(
      `SELECT count(*)::int AS n FROM identity_provider_events
       WHERE provider=$1 AND event_id LIKE $2`,
      [this.provider, prefix + "%"],
    );
    return res.rows[0].n;
  }
}

export function createPool(connectionString) {
  return new pg.Pool({ connectionString, max: 10 });
}
