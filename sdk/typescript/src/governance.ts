/**
 * WhitePact runtime governance HTTP helpers (TypeScript SDK P1-03).
 */

export type GovernanceToolCallResult = Record<string, unknown>;
export type GovernanceRequestOptions = { signal?: AbortSignal };
import { validateBaseUrl } from "./transport.js";

/**
 * The server did not return a governance answer (non-2xx, or a body that is not a JSON object).
 *
 * Thrown rather than returned: a 401, 403, 429 or 5xx carries no `governance_denied` or
 * `governance_approval_required` marker, so a caller that proceeds when neither is present would
 * read the failure as "not blocked".
 */
export class GovernanceRequestError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(`governance request failed [${status}]: ${detail}`);
    this.name = "GovernanceRequestError";
  }
}

/** A result envelope without contradictory markers; ALLOW alone is not execution. */
export function isCompleted(result: GovernanceToolCallResult): boolean {
  return completedEnvelope(result, 0);
}

function completedEnvelope(result: GovernanceToolCallResult, depth: number): boolean {
  if (depth >= 128) return false;
  if (result === null || typeof result !== "object" || Array.isArray(result)
    || !Object.prototype.hasOwnProperty.call(result, "result") || "error" in result) return false;
  const owns = (field: string) => Object.prototype.hasOwnProperty.call(result, field);
  for (const field of ["reconciliation_required", "denied", "requires_approval", "quarantined",
    "failed", "pending", "is_error", "isError"])
    if (owns(field) && result[field] !== false) return false;
  for (const field of ["status", "outcome_status"]) {
    if (!owns(field)) continue;
    if (field === "outcome_status" && result[field] === null) continue;
    if (result[field] !== "SUCCEEDED") return false;
  }
  if (owns("decision") && result.decision !== "ALLOW" && result.decision !== "ALLOW_WITH_REDACTION") return false;
  const payload = result.result;
  if (payload && typeof payload === "object" && !Array.isArray(payload)) {
    const nested = payload as GovernanceToolCallResult;
    const has = (field: string) => Object.prototype.hasOwnProperty.call(nested, field);
    if (has("error") || ["is_error", "isError"].some(field => has(field) && nested[field] !== false)) return false;
    if (["result", "status", "outcome_status", "decision", "reconciliation_required", "denied",
      "requires_approval", "quarantined", "failed", "pending"].some(has)) return completedEnvelope(nested, depth + 1);
  }
  return true;
}

function resourceId(value: string): string {
  // Reject rather than trim or normalize: the server-issued ID is the binding.
  if (typeof value !== "string" || !value || value === "." || value === ".."
    || /[\s\p{Cc}/\\?#%]/u.test(value))
    throw new TypeError("Invalid resource identifier");
  try { return encodeURIComponent(value); }
  catch { throw new TypeError("Invalid resource identifier"); }
}

export class GovernanceRuntimeClient {
  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly timeout: number;

  constructor(options: { apiKey: string; baseUrl?: string; timeout?: number }) {
    this.baseUrl = (options.baseUrl ?? "http://localhost:8765").replace(/\/$/, "");
    this.apiKey = options.apiKey;
    validateBaseUrl(this.baseUrl, this.apiKey);
    this.timeout = options.timeout ?? 30_000;
    if (!Number.isFinite(this.timeout) || this.timeout <= 0 || this.timeout > 2147483647)
      throw new RangeError("SDK timeout must be positive, finite and within the timer range");
  }

  private headers(): Record<string, string> {
    return {
      Authorization: `Bearer ${this.apiKey}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    };
  }

  private url(path: string): string {
    return `${this.baseUrl}/api/${path.replace(/^\//, "")}`;
  }

  private async request(
    path: string,
    method: "GET" | "POST",
    payload?: unknown,
    options: GovernanceRequestOptions = {},
  ): Promise<Record<string, unknown>> {
    const controller = new AbortController();
    const cancel = () => controller.abort(new DOMException("Request canceled; mutation outcome may be unknown", "AbortError"));
    if (options.signal?.aborted) { cancel(); throw controller.signal.reason; }
    options.signal?.addEventListener("abort", cancel, { once: true });
    const timer = setTimeout(() => controller.abort(new DOMException("Request deadline exceeded; mutation outcome may be unknown", "AbortError")), this.timeout);
    // Cancellation must settle the public call even when a transport/body reader
    // does not settle on abort. Keep the deadline across headers and full body.
    let rejectAborted!: () => void;
    const aborted = new Promise<never>((_resolve, reject) => {
      rejectAborted = () => reject(controller.signal.reason);
      controller.signal.addEventListener("abort", rejectAborted, { once: true });
    });
    try {
      const res = await Promise.race([fetch(this.url(path), {
        method,
        headers: this.headers(),
        body: payload === undefined ? undefined : JSON.stringify(payload),
        signal: controller.signal,
        redirect: "error",
      }), aborted]);
      if (!res.ok) {
        const text = await Promise.race([res.text(), aborted]);
        const detail = this.apiKey ? text.split(this.apiKey).join("[REDACTED]") : text;
        throw new GovernanceRequestError(res.status, detail.slice(0, 200));
      }
      let body: unknown;
      try {
        body = await Promise.race([res.json(), aborted]);
      } catch {
        if (controller.signal.aborted) throw controller.signal.reason;
        throw new GovernanceRequestError(res.status, "response is not JSON");
      }
      if (body === null || typeof body !== "object" || Array.isArray(body)) {
        throw new GovernanceRequestError(res.status, "response is not a JSON object");
      }
      return body as GovernanceToolCallResult;
    } catch (error) {
      if (controller.signal.aborted) throw controller.signal.reason;
      if (error instanceof Error && this.apiKey && error.message.includes(this.apiKey)) {
        const sanitized = new Error(error.message.split(this.apiKey).join("[REDACTED]"));
        sanitized.name = error.name;
        throw sanitized;
      }
      throw error;
    } finally {
      clearTimeout(timer);
      controller.signal.removeEventListener("abort", rejectAborted);
      options.signal?.removeEventListener("abort", cancel);
    }
  }

  async callTool(name: string, args: Record<string, unknown> = {}, purpose = "sdk-governance", options?: GovernanceRequestOptions): Promise<GovernanceToolCallResult> {
    return this.request("v1/governance/tools/call", "POST", { name, arguments: args, purpose }, options);
  }

  async listApprovals(status?: string, options?: GovernanceRequestOptions): Promise<Record<string, unknown>> {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    return this.request(`governance/approvals${qs}`, "GET", undefined, options);
  }

  /** Reads configured tenant policy; never grants execution authority. */
  async getPolicy(options?: GovernanceRequestOptions): Promise<Record<string, unknown>> {
    return this.request("governance/policy", "GET", undefined, options);
  }

  async resolveApproval(
    approvalId: string,
    outcome: string,
    notes?: string,
    options?: GovernanceRequestOptions,
  ): Promise<Record<string, unknown>> {
    return this.request(`governance/approvals/${resourceId(approvalId)}/resolve`, "POST", { outcome, ...(notes ? { notes } : {}) }, options);
  }

  async revokeDelegation(identityId: string, reason: string, options?: GovernanceRequestOptions): Promise<Record<string, unknown>> {
    return this.request(`governance/delegations/${resourceId(identityId)}/revoke`, "POST", { reason }, options);
  }

  async executeApproval(approvalId: string, options?: GovernanceRequestOptions): Promise<Record<string, unknown>> {
    return this.request(`governance/approvals/${resourceId(approvalId)}/execute`, "POST", {}, options);
  }

  async getEvidence(evidenceId: string, options?: GovernanceRequestOptions): Promise<Record<string, unknown>> {
    // Legacy route is unavailable in the current backend. Use getAttestation instead.
    return this.request(`governance/evidence/${resourceId(evidenceId)}`, "GET", undefined, options);
  }

  async listEvidence(limit = 50, options?: GovernanceRequestOptions): Promise<Record<string, unknown>> {
    if (!Number.isInteger(limit) || limit < 1 || limit > 200)
      throw new RangeError("Evidence limit must be an integer from 1 to 200");
    return this.request(`governance/evidence?limit=${limit}`, "GET", undefined, options);
  }

  async getAttestation(evidenceId: string, options?: GovernanceRequestOptions): Promise<Record<string, unknown>> {
    return this.request(`governance/evidence/${resourceId(evidenceId)}/attestation`, "GET", undefined, options);
  }
}
