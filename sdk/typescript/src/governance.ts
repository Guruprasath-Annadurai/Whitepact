/**
 * WhitePact runtime governance HTTP helpers (TypeScript SDK P1-03).
 */

export type GovernanceToolCallResult = Record<string, unknown>;
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

/** Error-free and not uncertain; absence of "denied" alone is not permission. */
export function isCompleted(result: GovernanceToolCallResult): boolean {
  return !("error" in result)
    && result.status !== "UNKNOWN"
    && result.outcome_status !== "UNKNOWN"
    && result.reconciliation_required !== true;
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

  async callTool(
    name: string,
    args: Record<string, unknown> = {},
    purpose = "sdk-governance",
  ): Promise<GovernanceToolCallResult> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);
    try {
      const res = await fetch(this.url("v1/governance/tools/call"), {
        method: "POST",
        headers: this.headers(),
        body: JSON.stringify({ name, arguments: args, purpose }),
        signal: controller.signal,
        redirect: "error",
      });
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        const detail = this.apiKey ? text.split(this.apiKey).join("[REDACTED]") : text;
        throw new GovernanceRequestError(res.status, detail.slice(0, 200));
      }
      let body: unknown;
      try {
        body = await res.json();
      } catch {
        throw new GovernanceRequestError(res.status, "response is not JSON");
      }
      if (body === null || typeof body !== "object" || Array.isArray(body)) {
        throw new GovernanceRequestError(res.status, "response is not a JSON object");
      }
      return body as GovernanceToolCallResult;
    } finally {
      clearTimeout(timer);
    }
  }

  async listApprovals(status?: string): Promise<Record<string, unknown>> {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    const res = await fetch(this.url(`governance/approvals${qs}`), {
      redirect: "error",
      headers: this.headers(),
    });
    if (!res.ok) throw new Error(`listApprovals failed: ${res.status}`);
    return (await res.json()) as Record<string, unknown>;
  }

  async resolveApproval(
    approvalId: string,
    outcome: string,
    notes?: string,
  ): Promise<Record<string, unknown>> {
    const res = await fetch(this.url(`governance/approvals/${approvalId}/resolve`), {
      redirect: "error",
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({ outcome, ...(notes ? { notes } : {}) }),
    });
    if (!res.ok) throw new Error(`resolveApproval failed: ${res.status}`);
    return (await res.json()) as Record<string, unknown>;
  }

  async revokeDelegation(identityId: string, reason: string): Promise<Record<string, unknown>> {
    const res = await fetch(this.url(`governance/delegations/${identityId}/revoke`), {
      redirect: "error",
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({ reason }),
    });
    if (!res.ok) throw new Error(`revokeDelegation failed: ${res.status}`);
    return (await res.json()) as Record<string, unknown>;
  }

  async executeApproval(approvalId: string): Promise<Record<string, unknown>> {
    const res = await fetch(this.url(`governance/approvals/${approvalId}/execute`), {
      redirect: "error",
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({}),
    });
    if (!res.ok) throw new Error(`executeApproval failed: ${res.status}`);
    return (await res.json()) as Record<string, unknown>;
  }

  async getEvidence(evidenceId: string): Promise<Record<string, unknown>> {
    const res = await fetch(this.url(`governance/evidence/${evidenceId}`), {
      redirect: "error",
      headers: this.headers(),
    });
    if (!res.ok) throw new Error(`getEvidence failed: ${res.status}`);
    return (await res.json()) as Record<string, unknown>;
  }
}
