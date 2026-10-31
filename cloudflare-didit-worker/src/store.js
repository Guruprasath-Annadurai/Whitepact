/**
 * Durable event store contract for Neon PostgreSQL.
 *
 * ACK (HTTP 2xx) is allowed ONLY after commitIdentityEvent succeeds.
 * On store failure → throw StoreUnavailableError → handler returns 503
 * so Didit retries (up to 2) and later reconciliation can catch residual loss.
 *
 * InMemoryIdentityStore simulates Neon unique + row-lock semantics for local tests.
 * SqlIdentityStore is the Neon SQL surface (not executed live in this worktree).
 */

import { payloadHashHex } from "./verify.js";
import { assertNoMediaInRecord, durableProjection } from "./redact.js";

export class StoreUnavailableError extends Error {
  constructor(message = "Identity store unavailable; reconcile later.") {
    super(message);
    this.name = "StoreUnavailableError";
    this.code = "IDENTITY_STORE_UNAVAILABLE";
    this.httpStatus = 503;
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

/**
 * Neon/schema-aligned SQL used by production Workers (Hyperdrive or Neon serverless).
 * Kept as strings for review; not auto-applied.
 */
export const SQL = {
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
  // Atomic commit pattern (transaction):
  // BEGIN;
  //   lock binding FOR UPDATE;
  //   SELECT prior event; if hash mismatch → abort PROVIDER_REPLAY;
  //   if prior exists same hash → return ALREADY_PROCESSED;
  //   INSERT event row(s);
  //   UPDATE identity_verifications outcome (no media columns);
  // COMMIT;
  // Only after COMMIT may the Worker return 2xx.
};

export class InMemoryIdentityStore {
  constructor({ provider = "didit-sandbox", failNext = 0 } = {}) {
    this.provider = provider;
    this.bindings = new Map(); // session_id -> {user_id, org_id, context_hash}
    this.events = new Map(); // event_key -> record
    this.verifications = new Map(); // session_id -> {status, user_id, org_id}
    this._failNext = failNext;
    this.committedAcks = [];
  }

  simulateUnavailable(n = 1) {
    this._failNext = n;
  }

  _maybeFail() {
    if (this._failNext > 0) {
      this._failNext -= 1;
      throw new StoreUnavailableError();
    }
  }

  bindSession({ sessionId, userId, orgId, contextHash }) {
    this._maybeFail();
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

  /**
   * Atomic durable commit. Must complete before HTTP 2xx.
   */
  commitIdentityEvent(event, { testDelivery = false } = {}) {
    this._maybeFail();

    const projection = durableProjection(event);
    assertNoMediaInRecord(projection);
    const digest = payloadHashHex(event);
    const eventKey = (testDelivery ? "test:" : "event:") + event.event_id;

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

    const statusMap = {
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
    const outcome = statusMap[event.status];
    if (!outcome) throw new TenantIsolationError("unsupported status"); // fail closed

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

    const v = this.verifications.get(event.session_id);
    if (v) {
      let next = outcome;
      if (v.status === "IDENTITY_VERIFIED" && outcome !== "VERIFIED") next = "SUSPENDED";
      if (next === "VERIFIED") v.status = "IDENTITY_VERIFIED";
      else if (next === "REJECTED") v.status = "REJECTED";
      else if (next === "SUSPENDED") v.status = "SUSPENDED";
      else v.status = "REVIEW_REQUIRED";
    }

    this.committedAcks.push(eventKey);
    return {
      status: outcome === "VERIFIED" ? "IDENTITY_VERIFIED" : outcome,
      duplicate: false,
      identity_transition: outcome === "VERIFIED",
      record,
    };
  }
}
