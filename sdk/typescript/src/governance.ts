/**
 * WhitePact runtime governance HTTP helpers (TypeScript SDK P1-03).
 */

export type GovernanceToolCallResult = Record<string, unknown>;

export class GovernanceRuntimeClient {
  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly timeout: number;

  constructor(options: { apiKey: string; baseUrl?: string; timeout?: number }) {
    this.baseUrl = (options.baseUrl ?? "http://localhost:8765").replace(/\/$/, "");
    this.apiKey = options.apiKey;
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
    const res = await fetch(this.url("v1/governance/tools/call"), {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({ name, arguments: args, purpose }),
      signal: controller.signal,
    });
    clearTimeout(timer);
    return (await res.json()) as GovernanceToolCallResult;
  }

  async listApprovals(status?: string): Promise<Record<string, unknown>> {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    const res = await fetch(this.url(`governance/approvals${qs}`), {
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
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({ outcome, ...(notes ? { notes } : {}) }),
    });
    if (!res.ok) throw new Error(`resolveApproval failed: ${res.status}`);
    return (await res.json()) as Record<string, unknown>;
  }

  async executeApproval(approvalId: string): Promise<Record<string, unknown>> {
    const res = await fetch(this.url(`governance/approvals/${approvalId}/execute`), {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({}),
    });
    if (!res.ok) throw new Error(`executeApproval failed: ${res.status}`);
    return (await res.json()) as Record<string, unknown>;
  }
}
