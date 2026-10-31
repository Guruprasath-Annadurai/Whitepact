/**
 * Smallest safe Cloudflare Workers ingress for Didit V3 webhooks.
 *
 * Critical ACK invariant:
 *   Never return 2xx until durable commitIdentityEvent has succeeded.
 *   Didit's sample "return 2xx fast; do heavy work async" pattern is REJECTED here.
 *
 * Recovery:
 *   StoreUnavailableError → HTTP 503 → Didit retries (~1m, ~4m).
 *   After provider retry exhaustion, operator reconciliation (read-only retrieve)
 *   must re-drive only with a freshly signed webhook or authenticated decision
 *   fetch + new signed event — never elevate from unsigned state.
 */

import { scrubForLogs } from "./redact.js";
import {
  ProofInvalidError,
  signEvent,
  verifyWebhook,
} from "./verify.js";
import {
  OutOfOrderError,
  RateLimitedError,
  ReplayConflictError,
  SessionUnknownError,
  StoreUnavailableError,
  TenantIsolationError,
} from "./store.js";

export { signEvent };

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

export function enrollmentFromEnv(env) {
  const environment = env.WHITEPACT_DIDIT_ENVIRONMENT || "";
  if (environment !== "sandbox" && environment !== "live") {
    throw new ProofInvalidError("Didit enrollment is incomplete.");
  }
  if (env.WHITEPACT_RUNTIME_MODE === "production" && environment === "sandbox") {
    throw new ProofInvalidError("Sandbox identity cannot qualify production.");
  }
  const required = [
    "WHITEPACT_DIDIT_WEBHOOK_SECRET",
    "WHITEPACT_DIDIT_WORKFLOW_ID",
    "WHITEPACT_DIDIT_APPLICATION_ID",
  ];
  for (const k of required) {
    if (!env[k]) throw new ProofInvalidError("Didit enrollment is incomplete.");
  }
  return {
    webhookSecret: env.WHITEPACT_DIDIT_WEBHOOK_SECRET,
    workflowId: env.WHITEPACT_DIDIT_WORKFLOW_ID,
    applicationId: env.WHITEPACT_DIDIT_APPLICATION_ID,
    environment,
  };
}

/**
 * @param {Request} request
 * @param {{ store: import("./store.js").InMemoryIdentityStore, env: Record<string,string>, now?: () => number, log?: Function }} ctx
 */
export async function handleDiditWebhook(request, ctx) {
  const { store, env, now, log = () => {} } = ctx;

  if (request.method !== "POST") {
    return jsonResponse(405, { error: "METHOD_NOT_ALLOWED" });
  }

  let enrollment;
  try {
    enrollment = enrollmentFromEnv(env);
  } catch (err) {
    return jsonResponse(403, { error: err.code || "DIDIT_PROOF_INVALID" });
  }

  const signature = request.headers.get("X-Signature-V2") || "";
  const timestamp = request.headers.get("X-Timestamp") || "";
  // Refuse Simple-only authentication for identity elevation.
  if (!signature && request.headers.get("X-Signature-Simple")) {
    return jsonResponse(403, { error: "DIDIT_PROOF_INVALID", detail: "V2_REQUIRED" });
  }

  const ab = await request.arrayBuffer();
  const payload = new Uint8Array(ab);

  let event;
  try {
    event = verifyWebhook({
      payload,
      signature,
      timestamp,
      webhookSecret: enrollment.webhookSecret,
      applicationId: enrollment.applicationId,
      environment: enrollment.environment,
      workflowId: enrollment.workflowId,
      testDelivery: request.headers.get("X-Didit-Test-Delivery") === "1",
      now,
    });
  } catch {
    log("deny", { reason: "proof_invalid" });
    return jsonResponse(403, { error: "DIDIT_PROOF_INVALID" });
  }

  // Log only scrubbed metadata — never raw decision / media.
  log("accepted_proof", scrubForLogs({
    event_id: event.event_id,
    session_id: event.session_id,
    status: event.status,
    webhook_type: event.webhook_type,
    environment: event.environment,
  }));

  const testDelivery = request.headers.get("X-Didit-Test-Delivery") === "1";

  try {
    // DURABLE COMMIT BEFORE ACK — do not defer to waitUntil().
    const result = store.commitIdentityEvent(event, { testDelivery });
    return jsonResponse(200, {
      ok: true,
      status: result.status,
      duplicate: result.duplicate,
      identity_transition: result.identity_transition,
      event_id: event.event_id,
    });
  } catch (err) {
    if (err instanceof StoreUnavailableError || err instanceof RateLimitedError) {
      log("store_unavailable", {
        event_id: event.event_id,
        reason: err.reason || err.code,
      });
      // 503 triggers Didit retries; do NOT claim success.
      return jsonResponse(503, {
        error: err.code,
        reconcile: true,
        reason: err.reason || undefined,
      });
    }
    if (
      err instanceof ReplayConflictError ||
      err instanceof TenantIsolationError ||
      err instanceof SessionUnknownError ||
      err instanceof OutOfOrderError ||
      err instanceof ProofInvalidError
    ) {
      return jsonResponse(err.httpStatus || 403, { error: err.code });
    }
    log("unexpected", { name: err?.name });
    return jsonResponse(503, { error: "IDENTITY_STORE_UNAVAILABLE", reconcile: true });
  }
}

/**
 * Simulate Didit delivery attempts: initial + up to 2 retries on 5xx.
 * After exhaustion, record deadletter — never elevate without a later signed success.
 */
export async function simulateDiditRetryBudget(postOnce, { maxRetries = 2 } = {}) {
  const attempts = [];
  for (let attempt = 1; attempt <= 1 + maxRetries; attempt++) {
    const res = await postOnce(attempt);
    const status = res.status;
    attempts.push({ attempt, status });
    if (status >= 200 && status < 300) {
      return { outcome: "delivered", attempts };
    }
    // Didit retries 5xx and 404 only; 4xx (non-404) stop.
    if (status === 404 || (status >= 500 && status <= 599)) {
      continue;
    }
    return { outcome: "no_retry", attempts };
  }
  return { outcome: "exhausted", attempts };
}

/** Minimal Worker export shape (local harness / future wrangler entry). */
export function createWorker(store) {
  return {
    async fetch(request, env) {
      return handleDiditWebhook(request, { store, env });
    },
  };
}
