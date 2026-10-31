/**
 * Durable event store contract for Neon PostgreSQL.
 *
 * ACK (HTTP 2xx) is allowed ONLY after commitIdentityEvent succeeds.
 * On store failure → throw StoreUnavailableError → handler returns 503
 * so Didit retries (up to 2) and later reconciliation can catch residual loss.
 *
 * InMemoryIdentityStore simulates Neon unique + row-lock + rollback semantics.
 */

import { payloadHashHex } from "./verify.js";
import { assertNoMediaInRecord, durableProjection } from "./redact.js";

export class StoreUnavailableError extends Error {
  constructor(message = "Identity store unavailable; reconcile later.", reason = "unavailable") {
    super(message);
    this.name = "StoreUnavailableError";
    this.code = "IDENTITY_STORE_UNAVAILABLE";
    this.httpStatus = 503;
    this.reason = reason;
  }
}

export class TenantIsolationError extends Error {
  constructor(message = "Active tenant context mismatch.") {
    super(message);
    this.name = "TenantIsolationError";
    this.code = "CROSS_TENANT";
    this.httpStatus = 403;
  }
}

export class ReplayConflictError extends Error {
  constructor(message = "Provider replay with mutated payload.") {
    super(message);
    this.name = "ReplayConflictError";
    this.code = "PROVIDER_REPLAY";
    this.httpStatus = 403;
  }
}

export class SessionUnknownError extends Error {
  constructor() {
    super("Verification session is unknown.");
    this.name = "SessionUnknownError";
    this.code = "VERIFICATION_SESSION_UNKNOWN";
    this.httpStatus = 403;
  }
}

export class OutOfOrderError extends Error {
  constructor(message = "Reconcile conflicting or older provider decisions.") {
    super(message);
    this.name = "OutOfOrderError";
    this.code = "PROVIDER_EVENT_OUT_OF_ORDER";
    this.httpStatus = 403;
  }
}

export class RateLimitedError extends Error {
  constructor(message = "Identity store rate limited; retry.") {
    super(message);
    this.name = "RateLimitedError";
    this.code = "IDENTITY_STORE_RATE_LIMITED";
    this.httpStatus = 503;
  }
}

/**
 * Neon/schema-aligned SQL used by production Workers (Hyperdrive or Neon serverless).
 * Kept as strings for review; not auto-applied.
 */
export const SQL = {
  begin: `BEGIN`,
  commit: `COMMIT`,
  rollback: `ROLLBACK`,
  insertInit: `
    INSERT INTO identity_session_bindings (
      provider, session_id, user_id, org_id, context_hash, created_at
    ) VALUES ($1, $2, $3, $4, $5, now())
    ON CONFLICT (provider, session_id) DO NOTHING
  `,
  lockBinding: `
    SELECT user_id, org_id, context_hash
    FROM identity_session_bindings
    WHERE provider = $1 AND session_id = $2
    FOR UPDATE
  `,
  selectEvent: `
    SELECT payload_hash FROM identity_provider_events
    WHERE provider = $1 AND event_id = $2
  `,
  insertEvent: `
    INSERT INTO identity_provider_events (
      id, provider, event_id, user_id, org_id, payload_hash,
      session_id, status, webhook_type, environment, received_at
    ) VALUES (
      gen_random_uuid()::text, $1, $2, $3, $4, $5,
      $6, $7, $8, $9, now()
    )
  `,
  insertOrderKey: `
    INSERT INTO identity_provider_events (
      id, provider, event_id, user_id, org_id, payload_hash,
      session_id, status, webhook_type, environment, received_at
    ) VALUES (
      gen_random_uuid()::text, $1, $2, $3, $4, $5,
      $6, $7, $8, $9, now()
    )
  `,
  updateVerification: `
    UPDATE identity_verifications
    SET status = $3, updated_at = now(),
        verified_at = CASE WHEN $3 = 'IDENTITY_VERIFIED' THEN now() ELSE verified_at END
    WHERE provider = $1 AND provider_reference_id = $2
  `,
  insertDeadletter: `
    INSERT INTO identity_reconciliation_deadletters (
      id, provider, event_id, session_id, reason, payload_hash, observed_at
    ) VALUES (gen_random_uuid()::text, $1, $2, $3, $4, $5, now())
  `,
};

const STATUS_MAP = {
  Approved: "VERIFIED",
  Declined: "REJECTED",
  "In Review": "REVIEW",
  "Not Started": "REVIEW",
  "In Progress": "REVIEW",
  Resubmitted: "REVIEW",
  Expired: "REJECTED",
  Abandoned: "REJECTED",
  "Kyc Expired": "SUSPENDED",
};

export class InMemoryIdentityStore {
  constructor({
    provider = "didit-sandbox",
    failNext = 0,
    suspended = false,
    connectLatencyMs = 0,
    connectTimeoutMs = 5_000,
    rateLimitRemaining = Infinity,
    abortCommitAfterEventInsert = false,
  } = {}) {
    this.provider = provider;
    this.bindings = new Map();
    this.events = new Map();
    this.verifications = new Map();
    this.deadletters = [];
    this._failNext = failNext;
    this.suspended = suspended;
    this.connectLatencyMs = connectLatencyMs;
    this.connectTimeoutMs = connectTimeoutMs;
    this.rateLimitRemaining = rateLimitRemaining;
    this.abortCommitAfterEventInsert = abortCommitAfterEventInsert;
    this.committedAcks = [];
    this.txnLog = []; // {op, rolledBack?}
    this._lock = Promise.resolve();
  }

  simulateUnavailable(n = 1) {
    this._failNext = n;
  }

  simulateSuspension(on = true) {
    this.suspended = on;
  }

  simulateConnectLatency(ms) {
    this.connectLatencyMs = ms;
  }

  simulateRateLimit(remaining) {
    this.rateLimitRemaining = remaining;
  }

  /**
   * Serialize commits like PG row lock on session binding.
   */
  async withLock(fn) {
    const prev = this._lock;
    let release;
    this._lock = new Promise((r) => {
      release = r;
    });
    await prev;
    try {
      return await fn();
    } finally {
      release();
    }
  }

  _gate() {
    if (this.suspended) {
      throw new StoreUnavailableError(
        "Neon compute suspended (quota/scale-to-zero blocked).",
        "suspended",
      );
    }
    if (this.connectLatencyMs > this.connectTimeoutMs) {
      throw new StoreUnavailableError(
        "Identity store connection timed out.",
        "timeout",
      );
    }
    if (this.rateLimitRemaining <= 0) {
      throw new RateLimitedError();
    }
    if (Number.isFinite(this.rateLimitRemaining)) {
      this.rateLimitRemaining -= 1;
    }
    if (this._failNext > 0) {
      this._failNext -= 1;
      throw new StoreUnavailableError("Simulated connection failure.", "connection_failure");
    }
  }

  bindSession({ sessionId, userId, orgId, contextHash }) {
    this._gate();
    if (this.bindings.has(sessionId)) {
      const b = this.bindings.get(sessionId);
      if (b.user_id !== userId || b.org_id !== orgId) {
        throw new TenantIsolationError("Provider session cannot be rebound.");
      }
      return { duplicate: true };
    }
    this.bindings.set(sessionId, {
      user_id: userId,
      org_id: orgId,
      context_hash: contextHash,
    });
    this.verifications.set(sessionId, {
      status: "REVIEW_REQUIRED",
      user_id: userId,
      org_id: orgId,
    });
    return { duplicate: false };
  }

  _latestCreatedAt(sessionId) {
    let latest = -1;
    for (const key of this.events.keys()) {
      // order keys: `${sessionId}:${created_at}:${event_id}`
      if (!key.startsWith(sessionId + ":")) continue;
      const parts = key.split(":");
      if (parts.length < 3) continue;
      const ts = Number(parts[1]);
      if (Number.isFinite(ts) && ts > latest) latest = ts;
    }
    return latest;
  }

  /**
   * Atomic durable commit. Must complete before HTTP 2xx.
   * Simulates BEGIN…FOR UPDATE…INSERT…UPDATE…COMMIT with rollback.
   */
  commitIdentityEvent(event, { testDelivery = false } = {}) {
    this._gate();

    const projection = durableProjection(event);
    assertNoMediaInRecord(projection);
    const digest = payloadHashHex(event);
    const eventKey = (testDelivery ? "test:" : "event:") + event.event_id;
    const txn = { ops: [], rolledBack: false };

    const rollback = () => {
      for (const op of [...txn.ops].reverse()) {
        if (op.type === "insert_event") this.events.delete(op.key);
        if (op.type === "insert_order") this.events.delete(op.key);
        if (op.type === "update_verification") {
          this.verifications.set(op.sessionId, op.prev);
        }
      }
      txn.rolledBack = true;
      this.txnLog.push(txn);
    };

    const stage = (op) => txn.ops.push(op);

    try {
      this.txnLog.push(txn);

      if (testDelivery) {
        const prior = this.events.get(eventKey);
        if (prior) {
          if (prior.payload_hash !== digest) throw new ReplayConflictError();
          return {
            status: "TEST_RECEIPT_ONLY",
            duplicate: true,
            identity_transition: false,
            record: prior,
          };
        }
        const record = {
          provider: this.provider,
          event_id: eventKey,
          payload_hash: digest,
          ...projection,
          identity_transition: false,
        };
        assertNoMediaInRecord(record);
        this.events.set(eventKey, record);
        stage({ type: "insert_event", key: eventKey });
        this.committedAcks.push(eventKey);
        return {
          status: "TEST_RECEIPT_ONLY",
          duplicate: false,
          identity_transition: false,
          record,
        };
      }

      const binding = this.bindings.get(event.session_id);
      if (!binding) throw new SessionUnknownError();
      if (binding.user_id !== event.vendor_data) throw new TenantIsolationError();

      const prior = this.events.get(eventKey);
      if (prior) {
        if (prior.payload_hash !== digest) throw new ReplayConflictError();
        return {
          status: "ALREADY_PROCESSED",
          duplicate: true,
          identity_transition: false,
          record: prior,
        };
      }

      // Out-of-order: reject created_at <= latest admitted for session (#244 parity).
      const latest = this._latestCreatedAt(event.session_id);
      if (event.created_at <= latest) {
        throw new OutOfOrderError();
      }

      const outcome = STATUS_MAP[event.status];
      if (!outcome) throw new TenantIsolationError("unsupported status");

      const record = {
        provider: this.provider,
        event_id: eventKey,
        user_id: binding.user_id,
        org_id: binding.org_id,
        payload_hash: digest,
        ...projection,
      };
      assertNoMediaInRecord(record);

      this.events.set(eventKey, record);
      stage({ type: "insert_event", key: eventKey });

      const orderKey = `${event.session_id}:${event.created_at}:${event.event_id}`;
      this.events.set(orderKey, {
        provider: this.provider,
        event_id: orderKey,
        payload_hash: digest,
        session_id: event.session_id,
        created_at: event.created_at,
      });
      stage({ type: "insert_order", key: orderKey });

      if (this.abortCommitAfterEventInsert) {
        // Simulate mid-txn failure after event insert (Neon blip / constraint).
        throw new StoreUnavailableError("Commit aborted after event insert.", "txn_abort");
      }

      const v = this.verifications.get(event.session_id);
      if (v) {
        const prev = { ...v };
        let next = outcome;
        if (v.status === "IDENTITY_VERIFIED" && outcome !== "VERIFIED") next = "SUSPENDED";
        if (next === "VERIFIED") v.status = "IDENTITY_VERIFIED";
        else if (next === "REJECTED") v.status = "REJECTED";
        else if (next === "SUSPENDED") v.status = "SUSPENDED";
        else v.status = "REVIEW_REQUIRED";
        stage({ type: "update_verification", sessionId: event.session_id, prev });
      }

      this.committedAcks.push(eventKey);
      return {
        status: outcome === "VERIFIED" ? "IDENTITY_VERIFIED" : outcome,
        duplicate: false,
        identity_transition: outcome === "VERIFIED",
        record,
      };
    } catch (err) {
      if (txn.ops.length) rollback();
      else this.txnLog.push(txn);
      throw err;
    }
  }

  /**
   * Read-only reconciliation. Never elevates identity without a signed webhook path.
   */
  reconcileSession(sessionId, { userId, orgId } = {}) {
    this._gate();
    const binding = this.bindings.get(sessionId);
    if (!binding) throw new SessionUnknownError();
    if (userId && binding.user_id !== userId) throw new TenantIsolationError();
    if (orgId && binding.org_id !== orgId) throw new TenantIsolationError();
    const verification = this.verifications.get(sessionId);
    const events = [];
    for (const [key, row] of this.events) {
      if (key.startsWith("event:") && row.session_id === sessionId) events.push(row);
    }
    return {
      session_id: sessionId,
      binding,
      verification_status: verification?.status ?? null,
      event_count: events.length,
      elevates: false,
      note: "read-only; unsigned retrieval must not change identity state",
    };
  }

  recordDeadletter({ eventId, sessionId, reason, payloadHash }) {
    this.deadletters.push({
      provider: this.provider,
      event_id: eventId,
      session_id: sessionId,
      reason,
      payload_hash: payloadHash,
      observed_at: Date.now(),
    });
  }
}
