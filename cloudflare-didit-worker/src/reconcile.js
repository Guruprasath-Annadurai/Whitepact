/**
 * Didit reconciliation engine — durable job state machine.
 *
 * CRITICAL SECURITY INVARIANTS (WhitePact / #244 DiditService.reconcile):
 * 1. Decision GET is authenticated observation only — NEVER elevates identity.
 * 2. Neon remains an event ledger / job store — NOT a second identity authority.
 * 3. Authoritative transitions still require authentic signed webhook admission
 *    via commitIdentityEvent (durable-before-ACK).
 * 4. `reconcile: true` on webhook 503 responses is only an operator hint.
 * 5. Tenant / principal / session / application / environment / workflow bindings
 *    are verified before any job reaches `validated` / `applied`.
 *
 * States: pending → scheduled → fetching → validated → applied
 *                              ↘ retryable_failure → scheduled (backoff)
 *                              ↘ terminal_manual
 */

import { createHash, randomUUID } from "node:crypto";
import {
  DiditClient,
  DiditClientError,
  validateDecision,
} from "./didit_client.js";
import { scrubForLogs } from "./redact.js";
import {
  SessionUnknownError,
  TenantIsolationError,
  StoreUnavailableError,
} from "./store.js";

export const RECONCILE_STATES = Object.freeze({
  PENDING: "pending",
  SCHEDULED: "scheduled",
  FETCHING: "fetching",
  VALIDATED: "validated",
  APPLIED: "applied",
  RETRYABLE_FAILURE: "retryable_failure",
  TERMINAL_MANUAL: "terminal_manual",
});

export const REQUIRED_ACTION =
  "Obtain or resend the authentic signed provider event.";

const MAX_ATTEMPTS = 5;
const BACKOFF_SECONDS = [30, 120, 300, 900, 1800];

function nowSec() {
  return Math.floor(Date.now() / 1000);
}

function decisionObservationHash(observation) {
  const body = JSON.stringify({
    session_id: observation.session_id,
    status: observation.status,
    workflow_id: observation.workflow_id,
    application_id: observation.application_id,
    environment: observation.environment,
    vendor_data: observation.vendor_data,
  });
  return createHash("sha256").update(body).digest("hex");
}

export class ReconcileError extends Error {
  constructor(code, message, { terminal = false, retryable = false } = {}) {
    super(message);
    this.name = "ReconcileError";
    this.code = code;
    this.terminal = terminal;
    this.retryable = retryable;
  }
}

/**
 * In-memory durable job store (parity with Neon table identity_reconciliation_jobs).
 * PgIdentityStore can implement the same interface later without elevating identity.
 */
export class InMemoryReconcileJobStore {
  constructor() {
    /** @type {Map<string, object>} */
    this.jobs = new Map();
  }

  createJob(input) {
    const id = input.id || randomUUID();
    if (this.jobs.has(id)) {
      throw new ReconcileError("RECONCILE_JOB_CONFLICT", "Job id already exists.", {
        terminal: true,
      });
    }
    // Idempotency: one open job per (provider, session_id, reason bucket).
    for (const job of this.jobs.values()) {
      if (
        job.provider === input.provider &&
        job.session_id === input.sessionId &&
        job.reason === input.reason &&
        job.state !== RECONCILE_STATES.APPLIED &&
        job.state !== RECONCILE_STATES.TERMINAL_MANUAL
      ) {
        return { job, duplicate: true };
      }
    }
    const job = {
      id,
      provider: input.provider,
      session_id: input.sessionId,
      user_id: input.userId,
      org_id: input.orgId,
      reason: input.reason || "operator",
      state: RECONCILE_STATES.PENDING,
      attempt_count: 0,
      last_error_class: null,
      provider_status: null,
      decision_hash: null,
      workflow_id: input.workflowId || null,
      application_id: input.applicationId || null,
      environment: input.environment || null,
      required_action: REQUIRED_ACTION,
      identity_transition: false,
      elevates: false,
      created_at: nowSec(),
      updated_at: nowSec(),
      next_attempt_at: nowSec(),
      meta: scrubForLogs(input.meta || {}),
    };
    this.jobs.set(id, job);
    return { job, duplicate: false };
  }

  getJob(id) {
    return this.jobs.get(id) || null;
  }

  listOpenJobs({ sessionId } = {}) {
    return [...this.jobs.values()].filter((j) => {
      if (sessionId && j.session_id !== sessionId) return false;
      return (
        j.state !== RECONCILE_STATES.APPLIED &&
        j.state !== RECONCILE_STATES.TERMINAL_MANUAL
      );
    });
  }

  saveJob(job) {
    job.updated_at = nowSec();
    this.jobs.set(job.id, job);
    return job;
  }
}

/**
 * Orchestrates authenticated decision retrieval without elevating identity.
 */
export class ReconcileEngine {
  /**
   * @param {object} opts
   * @param {import("./store.js").InMemoryIdentityStore} opts.identityStore
   * @param {DiditClient} opts.client
   * @param {InMemoryReconcileJobStore} [opts.jobStore]
   * @param {object} [opts.enrollment] application/workflow/environment
   * @param {number} [opts.maxAttempts]
   */
  constructor({
    identityStore,
    client,
    jobStore = new InMemoryReconcileJobStore(),
    enrollment = {},
    maxAttempts = MAX_ATTEMPTS,
  }) {
    if (!identityStore || !client) {
      throw new ReconcileError("RECONCILE_MISCONFIGURED", "store and client required", {
        terminal: true,
      });
    }
    this.identityStore = identityStore;
    this.client = client;
    this.jobStore = jobStore;
    this.enrollment = enrollment;
    this.maxAttempts = maxAttempts;
  }

  /**
   * Enqueue reconciliation after missed webhook / exhausted retries / operator.
   * Does not call Didit yet.
   */
  enqueue({
    sessionId,
    userId,
    orgId,
    reason = "missed_or_exhausted",
    meta = {},
  }) {
    this._assertBinding(sessionId, userId, orgId);
    return this.jobStore.createJob({
      provider: this.identityStore.provider,
      sessionId,
      userId,
      orgId,
      reason,
      workflowId: this.enrollment.workflowId || this.client.workflowId,
      applicationId: this.enrollment.applicationId || this.client.applicationId,
      environment: this.enrollment.environment || this.client.environment,
      meta,
    });
  }

  /**
   * Drain deadletters into reconcile jobs (still non-elevating).
   */
  enqueueFromDeadletters() {
    const created = [];
    const letters = this.identityStore.deadletters || [];
    for (const dl of letters) {
      if (!dl.session_id) continue;
      const binding = this.identityStore.bindings.get(dl.session_id);
      if (!binding) continue;
      const { job, duplicate } = this.enqueue({
        sessionId: dl.session_id,
        userId: binding.user_id,
        orgId: binding.org_id,
        reason: `deadletter:${dl.reason || "unknown"}`,
        meta: { event_id: dl.event_id || null, payload_hash: dl.payload_hash || null },
      });
      if (!duplicate) created.push(job);
    }
    return created;
  }

  _assertBinding(sessionId, userId, orgId) {
    const binding = this.identityStore.bindings.get(sessionId);
    if (!binding) throw new SessionUnknownError();
    if (binding.user_id !== userId) throw new TenantIsolationError();
    if (binding.org_id !== orgId) throw new TenantIsolationError();
    const verification = this.identityStore.verifications.get(sessionId);
    // Revoked / hard-rejected sessions still allow observation but mark terminal
    // if operator tries to treat reconcile as re-open — handled in advance().
    return { binding, verification };
  }

  /**
   * Advance one job one step. Idempotent for applied/terminal.
   * @returns {object} job snapshot (never elevates)
   */
  async advance(jobId) {
    const job = this.jobStore.getJob(jobId);
    if (!job) {
      throw new ReconcileError("RECONCILE_JOB_UNKNOWN", "Unknown reconcile job.", {
        terminal: true,
      });
    }
    if (
      job.state === RECONCILE_STATES.APPLIED ||
      job.state === RECONCILE_STATES.TERMINAL_MANUAL
    ) {
      return this._snapshot(job);
    }

    try {
      this.identityStore._gate?.();
    } catch (err) {
      if (err instanceof StoreUnavailableError) {
        return this._failRetryable(job, "IDENTITY_STORE_UNAVAILABLE", err.message);
      }
      throw err;
    }

    let binding;
    let verification;
    try {
      ({ binding, verification } = this._assertBinding(
        job.session_id,
        job.user_id,
        job.org_id,
      ));
    } catch (err) {
      return this._failTerminal(job, err.code || "BINDING_FAILED", err.message);
    }

    if (verification?.status === "REJECTED") {
      return this._failTerminal(
        job,
        "SESSION_REVOKED_OR_REJECTED",
        "Verification is REJECTED; unsigned decision cannot reopen identity.",
      );
    }

    // Schedule gate
    if (
      job.state === RECONCILE_STATES.PENDING ||
      job.state === RECONCILE_STATES.RETRYABLE_FAILURE ||
      job.state === RECONCILE_STATES.SCHEDULED
    ) {
      if (job.next_attempt_at > nowSec()) {
        job.state = RECONCILE_STATES.SCHEDULED;
        this.jobStore.saveJob(job);
        return this._snapshot(job);
      }
      job.state = RECONCILE_STATES.FETCHING;
      job.attempt_count += 1;
      this.jobStore.saveJob(job);
    }

    if (job.attempt_count > this.maxAttempts) {
      return this._failTerminal(
        job,
        "RECONCILE_ATTEMPTS_EXHAUSTED",
        "Manual operator intervention required.",
      );
    }

    let decision;
    try {
      decision = await this.client.retrieveDecision(job.session_id);
    } catch (err) {
      return this._classifyClientFailure(job, err);
    }

    job.state = RECONCILE_STATES.FETCHING;

    let observation;
    try {
      observation = validateDecision(decision, {
        sessionId: job.session_id,
        vendorData: binding.user_id,
        workflowId: job.workflow_id || this.client.workflowId,
        applicationId: job.application_id || this.client.applicationId,
        environment: job.environment || this.client.environment,
      });
    } catch (err) {
      const code = err.code || "DIDIT_DECISION_INVALID";
      // Binding / assurance failures are terminal (fail-closed).
      if (
        code === "CROSS_TENANT" ||
        code === "DIDIT_DECISION_MISMATCH" ||
        code === "ASSURANCE_NOT_APPROVED" ||
        code === "DIDIT_DECISION_INVALID"
      ) {
        return this._failTerminal(job, code, err.message);
      }
      return this._classifyClientFailure(job, err);
    }

    // Chronological / conflict awareness: if local status conflicts with provider
    // observation, still do NOT elevate or suspend from unsigned decision —
    // record conflict and require signed event (#244 required_action).
    const localStatus = verification?.status ?? null;
    const localProofing = verification?.provider_proofing_status ?? null;
    const conflict =
      (localStatus === "IDENTITY_VERIFIED" || localProofing === "PROVIDER_APPROVED") &&
      observation.status &&
      observation.status !== "Approved";

    job.state = RECONCILE_STATES.VALIDATED;
    job.provider_status = observation.status;
    job.decision_hash = decisionObservationHash(observation);
    job.identity_transition = false;
    job.elevates = false;
    job.required_action = REQUIRED_ACTION;
    job.meta = scrubForLogs({
      ...(job.meta || {}),
      local_status: localStatus,
      conflict: Boolean(conflict),
      observation,
    });
    this.jobStore.saveJob(job);

    // "applied" = durable non-elevating observation committed. Identity unchanged.
    job.state = RECONCILE_STATES.APPLIED;
    job.last_error_class = conflict ? "CONFLICTING_DECISION_OBSERVED" : null;
    this.jobStore.saveJob(job);

    // Local snap (existing read-only helper) — still elevates: false.
    const snap = this.identityStore.reconcileSession(job.session_id, {
      userId: job.user_id,
      orgId: job.org_id,
    });
    if (snap.elevates !== false) {
      return this._failTerminal(
        job,
        "RECONCILE_INVARIANT_BROKEN",
        "reconcileSession attempted elevation — fail closed.",
      );
    }

    return this._snapshot(job);
  }

  /**
   * Convenience: enqueue + advance until applied/terminal/scheduled wait.
   */
  async reconcileSession({ sessionId, userId, orgId, reason = "operator" }) {
    const { job } = this.enqueue({ sessionId, userId, orgId, reason });
    let snap = await this.advance(job.id);
    // Single automatic follow-up if we only flipped into fetching mid-flight
    // (advance already completes fetch in one call). Loop for scheduled→ready.
    let guard = 0;
    while (
      snap.state === RECONCILE_STATES.RETRYABLE_FAILURE &&
      snap.next_attempt_at <= nowSec() &&
      guard < this.maxAttempts
    ) {
      guard += 1;
      snap = await this.advance(job.id);
    }
    return snap;
  }

  _classifyClientFailure(job, err) {
    const code = err?.code || "DIDIT_UNAVAILABLE";
    const retryable =
      err?.retryable === true ||
      code === "DIDIT_UNAVAILABLE" ||
      code === "DIDIT_TIMEOUT" ||
      code === "DIDIT_RATE_LIMITED";
    if (retryable) {
      return this._failRetryable(job, code, err.message || code);
    }
    return this._failTerminal(job, code, err.message || code);
  }

  _failRetryable(job, code, message) {
    job.state = RECONCILE_STATES.RETRYABLE_FAILURE;
    job.last_error_class = code;
    job.identity_transition = false;
    job.elevates = false;
    const delay = BACKOFF_SECONDS[Math.min(job.attempt_count, BACKOFF_SECONDS.length) - 1] || 30;
    job.next_attempt_at = nowSec() + delay;
    job.meta = scrubForLogs({ ...(job.meta || {}), last_error_message: message });
    if (job.attempt_count >= this.maxAttempts) {
      return this._failTerminal(job, "RECONCILE_ATTEMPTS_EXHAUSTED", message);
    }
    this.jobStore.saveJob(job);
    return this._snapshot(job);
  }

  _failTerminal(job, code, message) {
    job.state = RECONCILE_STATES.TERMINAL_MANUAL;
    job.last_error_class = code;
    job.identity_transition = false;
    job.elevates = false;
    job.required_action = REQUIRED_ACTION;
    job.meta = scrubForLogs({ ...(job.meta || {}), last_error_message: message });
    this.jobStore.saveJob(job);
    return this._snapshot(job);
  }

  _snapshot(job) {
    return {
      job_id: job.id,
      session_id: job.session_id,
      state: job.state,
      provider_status: job.provider_status,
      decision_hash: job.decision_hash,
      attempt_count: job.attempt_count,
      last_error_class: job.last_error_class,
      next_attempt_at: job.next_attempt_at,
      identity_transition: false,
      elevates: false,
      required_action: job.required_action || REQUIRED_ACTION,
      reason: job.reason,
      // Explicit: observation must never be confused with recovery-complete.
      recovery_complete: false,
      signed_webhook_required: true,
    };
  }
}

/**
 * Factory from enrollment env vars (secrets must come from Wrangler — never git).
 */
export function createReconcileEngineFromEnv(identityStore, env, { fetchImpl } = {}) {
  const client = new DiditClient({
    apiKey: env.WHITEPACT_DIDIT_API_KEY || "",
    applicationId: env.WHITEPACT_DIDIT_APPLICATION_ID || "",
    workflowId: env.WHITEPACT_DIDIT_WORKFLOW_ID || "",
    environment: env.WHITEPACT_DIDIT_ENVIRONMENT || "sandbox",
    fetchImpl,
  });
  return new ReconcileEngine({
    identityStore,
    client,
    enrollment: {
      applicationId: env.WHITEPACT_DIDIT_APPLICATION_ID,
      workflowId: env.WHITEPACT_DIDIT_WORKFLOW_ID,
      environment: env.WHITEPACT_DIDIT_ENVIRONMENT,
    },
  });
}

export { DiditClient, DiditClientError, validateDecision };
