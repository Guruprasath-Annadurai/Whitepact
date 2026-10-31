/**
 * Didit V3 authenticated API client (decision retrieve + webhook delivery ops).
 *
 * Security model (#244 DiditProvider parity):
 * - Session IDs must be well-formed UUIDs before any secret-bearing request.
 * - No redirects; size-capped bodies; duplicate-key-rejecting JSON parse.
 * - Decision fetch is NEVER an identity elevation authority.
 * - Webhook list/resend helpers are optional management APIs — entitlement
 *   is account-specific; do not assume founder keys have these scopes.
 *
 * Transport is injectable for mocked tests (no real Didit / no billable ops).
 */

import { parseJsonStrict, MAX_BYTES } from "./parse.js";
import { scrubForLogs } from "./redact.js";

export const DIDIT_API_BASE = "https://verification.didit.me/v3/";
export const DEFAULT_TIMEOUT_MS = 10_000;
export const MAX_RESPONSE_BYTES = 2_000_000;

export class DiditClientError extends Error {
  constructor(code, message, { httpStatus = 503, retryable = false, cause } = {}) {
    super(message);
    this.name = "DiditClientError";
    this.code = code;
    this.httpStatus = httpStatus;
    this.retryable = retryable;
    if (cause) this.cause = cause;
  }
}

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function assertSessionUuid(sessionId) {
  if (typeof sessionId !== "string" || !UUID_RE.test(sessionId)) {
    throw new DiditClientError("DIDIT_SESSION_INVALID", "session_id must be a UUID", {
      httpStatus: 403,
      retryable: false,
    });
  }
}

/**
 * Classify HTTP / transport failures into safe operator buckets.
 */
export function classifyDiditHttpError(status, bodyText = "") {
  if (status === 401 || status === 403) {
    return new DiditClientError(
      "DIDIT_CREDENTIALS_INVALID",
      "Didit API rejected credentials or scope.",
      { httpStatus: status, retryable: false },
    );
  }
  if (status === 404) {
    return new DiditClientError(
      "DIDIT_SESSION_NOT_FOUND",
      "Didit session/decision not found for key scope.",
      { httpStatus: 404, retryable: false },
    );
  }
  if (status === 429) {
    return new DiditClientError(
      "DIDIT_RATE_LIMITED",
      "Didit API rate limited.",
      { httpStatus: 429, retryable: true },
    );
  }
  if (status >= 500 || status === 408) {
    return new DiditClientError(
      "DIDIT_UNAVAILABLE",
      "Didit service unavailable; reconcile later.",
      { httpStatus: 503, retryable: true },
    );
  }
  return new DiditClientError(
    "DIDIT_RESPONSE_INVALID",
    `Unexpected Didit HTTP ${status}${bodyText ? ": " + bodyText.slice(0, 80) : ""}`,
    { httpStatus: status >= 400 ? status : 502, retryable: false },
  );
}

function encodePath(segments) {
  return segments.map((s) => encodeURIComponent(s)).join("/");
}

/**
 * @typedef {object} DiditClientOptions
 * @property {string} apiKey
 * @property {string} [applicationId]
 * @property {string} [workflowId]
 * @property {"sandbox"|"live"} [environment]
 * @property {(input: RequestInfo, init?: RequestInit) => Promise<Response>} [fetchImpl]
 * @property {number} [timeoutMs]
 * @property {string} [baseUrl]
 */

export class DiditClient {
  /**
   * @param {DiditClientOptions} opts
   */
  constructor({
    apiKey,
    applicationId = "",
    workflowId = "",
    environment = "sandbox",
    fetchImpl = globalThis.fetch,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    baseUrl = DIDIT_API_BASE,
  } = {}) {
    if (!apiKey || typeof apiKey !== "string") {
      throw new DiditClientError(
        "DIDIT_NOT_ENROLLED",
        "Didit API key missing; client not enrolled.",
        { httpStatus: 403, retryable: false },
      );
    }
    if (environment !== "sandbox" && environment !== "live") {
      throw new DiditClientError("DIDIT_NOT_ENROLLED", "Invalid Didit environment.", {
        httpStatus: 403,
        retryable: false,
      });
    }
    this.apiKey = apiKey;
    this.applicationId = applicationId;
    this.workflowId = workflowId;
    this.environment = environment;
    this.fetchImpl = fetchImpl;
    this.timeoutMs = timeoutMs;
    this.baseUrl = baseUrl.endsWith("/") ? baseUrl : baseUrl + "/";
  }

  /**
   * Low-level JSON GET/POST. Never follows redirects. Caps response size.
   */
  async request(method, path, { body = undefined } = {}) {
    const url = this.baseUrl + path.replace(/^\//, "");
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const init = {
        method,
        headers: {
          "x-api-key": this.apiKey,
          Accept: "application/json",
        },
        redirect: "error",
        signal: controller.signal,
      };
      if (body !== undefined) {
        init.headers["content-type"] = "application/json";
        init.body = JSON.stringify(body);
      }
      let res;
      try {
        res = await this.fetchImpl(url, init);
      } catch (err) {
        const aborted = err?.name === "AbortError";
        throw new DiditClientError(
          aborted ? "DIDIT_TIMEOUT" : "DIDIT_UNAVAILABLE",
          aborted
            ? "Didit request timed out; reconcile later."
            : "Didit transport failure; reconcile later.",
          { httpStatus: 503, retryable: true, cause: err },
        );
      }
      const buf = new Uint8Array(await res.arrayBuffer());
      if (buf.byteLength > MAX_RESPONSE_BYTES || buf.byteLength > MAX_BYTES) {
        throw new DiditClientError(
          "DIDIT_RESPONSE_OVERSIZED",
          "Didit response exceeds safe size cap.",
          { httpStatus: 502, retryable: false },
        );
      }
      if (!res.ok) {
        let text = "";
        try {
          text = new TextDecoder("utf-8").decode(buf).slice(0, 200);
        } catch {
          text = "";
        }
        throw classifyDiditHttpError(res.status, text);
      }
      if (buf.byteLength === 0) {
        throw new DiditClientError("DIDIT_RESPONSE_INVALID", "Empty Didit response.", {
          httpStatus: 502,
          retryable: false,
        });
      }
      let data;
      try {
        data = parseJsonStrict(buf);
      } catch (err) {
        throw new DiditClientError(
          "DIDIT_RESPONSE_INVALID",
          "Didit response JSON invalid or duplicate keys.",
          { httpStatus: 502, retryable: false, cause: err },
        );
      }
      if (!data || typeof data !== "object" || Array.isArray(data)) {
        throw new DiditClientError(
          "DIDIT_RESPONSE_INVALID",
          "Didit response must be a JSON object.",
          { httpStatus: 502, retryable: false },
        );
      }
      return data;
    } finally {
      clearTimeout(timer);
    }
  }

  /**
   * GET /v3/session/{sessionId}/decision/
   * Returns provider decision object. Caller must validate bindings.
   */
  async retrieveDecision(sessionId) {
    assertSessionUuid(sessionId);
    return this.request("GET", encodePath(["session", sessionId, "decision"]) + "/");
  }

  /**
   * Optional management API — list deliveries for a destination.
   * Evidence only: entitlement may be absent for sandbox keys.
   * GET /v3/webhook/destinations/{destinationUuid}/deliveries/
   */
  async listWebhookDeliveries(destinationUuid, { cursor } = {}) {
    assertSessionUuid(destinationUuid);
    const q = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
    return this.request(
      "GET",
      encodePath(["webhook", "destinations", destinationUuid, "deliveries"]) + "/" + q,
    );
  }

  /**
   * Optional management API — resend a past delivery (freshly signed by Didit).
   * POST /v3/webhook/destinations/{destinationUuid}/deliveries/{deliveryUuid}/resend/
   * Does NOT elevate identity locally; elevation only if resulting signed webhook
   * is admitted through the durable webhook path.
   */
  async resendWebhookDelivery(destinationUuid, deliveryUuid) {
    assertSessionUuid(destinationUuid);
    assertSessionUuid(deliveryUuid);
    return this.request(
      "POST",
      encodePath([
        "webhook",
        "destinations",
        destinationUuid,
        "deliveries",
        deliveryUuid,
        "resend",
      ]) + "/",
    );
  }
}

/**
 * Validate decision against enrolled bindings + optional webhook event fields.
 * Never returns media; strips to safe observation fields for persistence.
 *
 * Mirrors #244 DiditProvider.validate_decision: Approved requires feature
 * arrays present and Approved, but those arrays are NOT persisted.
 */
export function validateDecision(decision, expected, { requireApprovedFeatures = true } = {}) {
  if (!decision || typeof decision !== "object") {
    throw new DiditClientError("DIDIT_DECISION_INVALID", "Decision missing.", {
      httpStatus: 403,
      retryable: false,
    });
  }

  const sessionId = expected.sessionId ?? expected.session_id;
  if (decision.session_id != null && sessionId && decision.session_id !== sessionId) {
    throw new DiditClientError("DIDIT_DECISION_MISMATCH", "session_id mismatch.", {
      httpStatus: 403,
      retryable: false,
    });
  }

  if (expected.workflowId && decision.workflow_id != null) {
    if (decision.workflow_id !== expected.workflowId) {
      throw new DiditClientError("DIDIT_DECISION_MISMATCH", "workflow_id mismatch.", {
        httpStatus: 403,
        retryable: false,
      });
    }
  }

  if (expected.vendorData != null && decision.vendor_data != null) {
    if (decision.vendor_data !== expected.vendorData) {
      throw new DiditClientError("CROSS_TENANT", "vendor_data / principal mismatch.", {
        httpStatus: 403,
        retryable: false,
      });
    }
  }

  if (expected.applicationId && decision.application_id != null) {
    if (decision.application_id !== expected.applicationId) {
      throw new DiditClientError("DIDIT_DECISION_MISMATCH", "application_id mismatch.", {
        httpStatus: 403,
        retryable: false,
      });
    }
  }

  if (expected.environment && decision.environment != null) {
    if (decision.environment !== expected.environment) {
      throw new DiditClientError("DIDIT_DECISION_MISMATCH", "environment mismatch.", {
        httpStatus: 403,
        retryable: false,
      });
    }
  }

  if (expected.status != null && decision.status != null) {
    if (decision.status !== expected.status) {
      throw new DiditClientError("DIDIT_DECISION_MISMATCH", "status mismatch vs signed event.", {
        httpStatus: 403,
        retryable: false,
      });
    }
  }

  const status = decision.status;
  if (typeof status !== "string" || !status) {
    throw new DiditClientError("DIDIT_DECISION_INVALID", "Decision status missing.", {
      httpStatus: 403,
      retryable: false,
    });
  }

  if (requireApprovedFeatures && status === "Approved") {
    for (const name of ["id_verifications", "liveness_checks", "face_matches"]) {
      const checks = decision[name];
      if (
        !Array.isArray(checks) ||
        checks.length === 0 ||
        checks.some((c) => !c || typeof c !== "object" || c.status !== "Approved")
      ) {
        throw new DiditClientError(
          "ASSURANCE_NOT_APPROVED",
          `Required Didit proofing check failed: ${name}`,
          { httpStatus: 403, retryable: false },
        );
      }
    }
  }

  // Safe observation only — never copy feature/media arrays.
  const observation = {
    session_id: decision.session_id ?? sessionId,
    status,
    workflow_id: decision.workflow_id ?? expected.workflowId ?? null,
    application_id: decision.application_id ?? expected.applicationId ?? null,
    environment: decision.environment ?? expected.environment ?? null,
    vendor_data: decision.vendor_data ?? expected.vendorData ?? null,
    session_kind: typeof decision.session_kind === "string" ? decision.session_kind : null,
  };

  // Defense: scrub any accidental leakage before return.
  return scrubForLogs(observation);
}

/**
 * Build a mock fetch that serves canned Didit responses (tests only).
 */
export function createMockDiditFetch(router) {
  return async (url, init = {}) => {
    const method = (init.method || "GET").toUpperCase();
    const u = String(url);
    const key = `${method} ${u}`;
    const handler =
      typeof router === "function"
        ? router
        : router[key] ||
          router[`${method} *`] ||
          Object.entries(router).find(([k]) => {
            if (!k.startsWith(method + " ")) return false;
            const pat = k.slice(method.length + 1);
            if (pat.endsWith("*")) return u.startsWith(pat.slice(0, -1));
            return pat === u;
          })?.[1];

    if (!handler) {
      return new Response(JSON.stringify({ detail: "mock miss" }), { status: 404 });
    }
    const out = await handler({ url: u, init, method });
    if (out instanceof Response) return out;
    const { status = 200, body = {}, headers = {} } = out;
    return new Response(typeof body === "string" ? body : JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json", ...headers },
    });
  };
}
