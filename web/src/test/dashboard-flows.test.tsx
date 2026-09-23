// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DashboardShell, type WebSession } from "../features/dashboard/DashboardShell";
import { DomainPage } from "../features/dashboard/DomainPage";
import { OnboardingPage } from "../features/onboarding/OnboardingPage";
import { OverviewPage } from "../features/dashboard/OverviewPage";
import App from "../App";
import { EvidenceContractPanel } from "../features/dashboard/CanonicalPanels";

const { openPaddleTransactionCheckout } = vi.hoisted(() => ({
  openPaddleTransactionCheckout: vi.fn(async () => undefined),
}));

vi.mock("../lib/paddleCheckout", () => ({
  openPaddleTransactionCheckout,
  extractPaddleTransactionId: (url: string) => new URL(url).searchParams.get("_ptxn") ?? "",
}));

const session: WebSession = {
  user: { full_name: "Ada Lovelace", email: "ada@example.com" },
  organization: { id: "org-1", name: "Analytical Engines", plan: "FREE" },
};

const approvalDetail = (overrides: Record<string, unknown> = {}) => ({
  approval_id: "appr-1", action_type: "test.counter.increment", target: "test.counter.increment",
  risk_tier: "HIGH", requester: "key-1", status: "PENDING", required_approvals: 1,
  current_vote_count: 0, votes: [], purpose: "automated-test",
  argument_summary: { argument_keys: ["amount"], argument_count: 1 },
  ...overrides,
});

describe("dashboard and onboarding", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("renders not found for an unknown dashboard domain", async () => {
    vi.spyOn(window, "fetch").mockResolvedValue(new Response(JSON.stringify(session), { status: 200 }));
    render(<MemoryRouter initialEntries={["/dashboard/not-a-domain"]}><App /></MemoryRouter>);
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("This boundary");
    expect(screen.queryByRole("heading", { name: /Security posture/i })).not.toBeInTheDocument();
  });

  it("shows only launch-ready dashboard destinations", async () => {
    vi.spyOn(window, "fetch").mockResolvedValue(
      new Response(JSON.stringify(session), { status: 200 }),
    );
    render(<MemoryRouter initialEntries={["/dashboard"]}><Routes><Route path="/dashboard" element={<DashboardShell />}><Route index element={<div>Overview content</div>} /></Route></Routes></MemoryRouter>);
    expect(await screen.findByText("Overview content")).toBeInTheDocument();
    for (const label of ["Overview", "API Keys", "Approvals", "Evidence", "Security", "Organization", "Members", "Billing"]) {
      expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
    }
    for (const hidden of ["Agents", "Policies", "Usage", "MCP", "Settings"]) {
      expect(screen.queryByRole("link", { name: hidden })).not.toBeInTheDocument();
    }
  });

  it("uses persisted summary data and renders the truthful empty state", async () => {
    vi.spyOn(window, "fetch").mockResolvedValue(new Response(JSON.stringify({
      decisions: 0, agents: 0, pending_approvals: 0, blocked_actions: 0,
      recent_governance: [], services: { "Policy engine": "configured" },
    }), { status: 200 }));
    const Parent = () => <Outlet context={session} />;
    render(<MemoryRouter initialEntries={["/dashboard"]}><Routes><Route element={<Parent />}><Route path="/dashboard" element={<OverviewPage />} /></Route></Routes></MemoryRouter>);
    expect(await screen.findByText("No governed activity yet")).toBeInTheDocument();
    expect(screen.getByText(/Connect your first agent/i)).toBeInTheDocument();
    expect(screen.getByText("configured")).toBeInTheDocument();
  });

  it("renders synchronized billing state and disables checkout when unconfigured", async () => {
    vi.spyOn(window, "fetch").mockResolvedValue(new Response(JSON.stringify({
      items: [{ plan: "FREE", subscription_status: "past_due", stripe_customer_id: null }],
      source: "organization_repository", billing_configured: false,
    }), { status: 200 }));
    const Parent = () => <Outlet context={session} />;
    render(<MemoryRouter initialEntries={["/dashboard/billing"]}><Routes><Route element={<Parent />}><Route path="/dashboard/:domain" element={<DomainPage />} /></Route></Routes></MemoryRouter>);
    expect(await screen.findByText("Subscription status: past_due")).toBeInTheDocument();
    expect(screen.getByText(/No paid entitlement is being advertised as active/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Choose Pro" })).toBeDisabled();
  });

  it("uses the Paddle customer binding as the subscription-management signal", async () => {
    vi.spyOn(window, "fetch").mockResolvedValue(new Response(JSON.stringify({
      items: [{ plan: "PRO", subscription_status: "active", paddle_customer_id: "ctm_paddle", stripe_customer_id: null }],
      source: "organization_repository", billing_configured: true,
    }), { status: 200 }));
    const Parent = () => <Outlet context={session} />;
    render(<MemoryRouter initialEntries={["/dashboard/billing"]}><Routes><Route element={<Parent />}><Route path="/dashboard/:domain" element={<DomainPage />} /></Route></Routes></MemoryRouter>);
    expect(await screen.findByRole("button", { name: "Manage, downgrade or cancel" })).toBeEnabled();
  });

  it("does not expose portal management without a Paddle customer", async () => {
    vi.spyOn(window, "fetch").mockResolvedValue(new Response(JSON.stringify({
      items: [{ plan: "PRO", subscription_status: "active", paddle_customer_id: null, stripe_customer_id: "cus_legacy" }],
      source: "organization_repository", billing_configured: true,
    }), { status: 200 }));
    const Parent = () => <Outlet context={session} />;
    render(<MemoryRouter initialEntries={["/dashboard/billing"]}><Routes><Route element={<Parent />}><Route path="/dashboard/:domain" element={<DomainPage />} /></Route></Routes></MemoryRouter>);
    expect(await screen.findByText(/management becomes available after a Paddle customer/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Manage, downgrade or cancel" })).not.toBeInTheDocument();
  });

  it("opens the Paddle portal without sending browser tenant authority", async () => {
    const pendingPortal = new Promise<Response>(() => undefined);
    const fetchMock = vi.spyOn(window, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({
        items: [{ plan: "PRO", subscription_status: "active", paddle_customer_id: "ctm_paddle" }],
        source: "organization_repository", billing_configured: true,
      }), { status: 200 }))
      .mockReturnValueOnce(pendingPortal);
    const Parent = () => <Outlet context={session} />;
    render(<MemoryRouter initialEntries={["/dashboard/billing"]}><Routes><Route element={<Parent />}><Route path="/dashboard/:domain" element={<DomainPage />} /></Route></Routes></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: "Manage, downgrade or cancel" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const [path, init] = fetchMock.mock.calls[1];
    expect(path).toBe("/api/v1/web/billing/portal");
    expect(init).toEqual(expect.objectContaining({ method: "POST" }));
    const body = JSON.parse(String(init?.body));
    expect(body).toEqual({});
    expect(body).not.toHaveProperty("organization_id");
  });

  it("sends only the supported plan enum to checkout", async () => {
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    openPaddleTransactionCheckout.mockClear();
    const fetchMock = vi.spyOn(window, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({
        items: [{ plan: "FREE", subscription_status: "inactive", paddle_customer_id: null }],
        source: "organization_repository", billing_configured: true,
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        checkout_url: "https://sandbox-buy.paddle.com/paddle/paddlejs/v2?_ptxn=txn_backend_created",
      }), { status: 200 }));
    const Parent = () => <Outlet context={session} />;
    render(<MemoryRouter initialEntries={["/dashboard/billing"]}><Routes><Route element={<Parent />}><Route path="/dashboard/:domain" element={<DomainPage />} /></Route></Routes></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: "Choose Pro" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const [path, init] = fetchMock.mock.calls[1];
    expect(path).toBe("/api/v1/web/billing/checkout");
    const body = JSON.parse(String(init?.body));
    expect(body).toEqual({ plan: "PRO" });
    expect(body).not.toHaveProperty("price_id");
    expect(body).not.toHaveProperty("organization_id");
    await waitFor(() => expect(openPaddleTransactionCheckout).toHaveBeenCalledWith(
      "https://sandbox-buy.paddle.com/paddle/paddlejs/v2?_ptxn=txn_backend_created",
    ));
    expect(assign).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it("does not grant entitlement locally when Paddle checkout opens", async () => {
    openPaddleTransactionCheckout.mockClear();
    vi.spyOn(window, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({
        items: [{ plan: "FREE", subscription_status: "inactive", paddle_customer_id: null }],
        source: "organization_repository", billing_configured: true,
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        checkout_url: "https://sandbox-buy.paddle.com/?_ptxn=txn_open_only",
      }), { status: 200 }));
    const Parent = () => <Outlet context={session} />;
    render(<MemoryRouter initialEntries={["/dashboard/billing"]}><Routes><Route element={<Parent />}><Route path="/dashboard/:domain" element={<DomainPage />} /></Route></Routes></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: "Choose Pro" }));
    await waitFor(() => expect(openPaddleTransactionCheckout).toHaveBeenCalled());
    expect(screen.getByText("FREE")).toBeInTheDocument();
    expect(screen.getByText(/Access changes only after a signed billing webhook/i)).toBeInTheDocument();
  });

  it("surfaces Paddle.js initialization failures without navigation", async () => {
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    openPaddleTransactionCheckout.mockRejectedValueOnce(new Error("Paddle client token is not configured."));
    vi.spyOn(window, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({
        items: [{ plan: "FREE", subscription_status: "inactive", paddle_customer_id: null }],
        source: "organization_repository", billing_configured: true,
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        checkout_url: "https://sandbox-buy.paddle.com/?_ptxn=txn_fail",
      }), { status: 200 }));
    const Parent = () => <Outlet context={session} />;
    render(<MemoryRouter initialEntries={["/dashboard/billing"]}><Routes><Route element={<Parent />}><Route path="/dashboard/:domain" element={<DomainPage />} /></Route></Routes></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: "Choose Pro" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/Paddle client token is not configured/i);
    expect(assign).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it.each([
    [401, "Your session has expired"],
    [404, "No Paddle customer subscription is available"],
    [503, "Billing management is temporarily unavailable"],
  ])("renders a safe portal error for HTTP %s", async (status, expected) => {
    vi.spyOn(window, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({
        items: [{ plan: "PRO", subscription_status: "active", paddle_customer_id: "ctm_paddle" }],
        source: "organization_repository", billing_configured: true,
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "provider internal detail" }), { status }));
    const Parent = () => <Outlet context={session} />;
    render(<MemoryRouter initialEntries={["/dashboard/billing"]}><Routes><Route element={<Parent />}><Route path="/dashboard/:domain" element={<DomainPage />} /></Route></Routes></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: "Manage, downgrade or cancel" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(expected);
    expect(screen.getByRole("button", { name: "Manage, downgrade or cancel" })).toBeEnabled();
  });

  it("renders backend-backed security status instead of static copy", async () => {
    vi.spyOn(window, "fetch").mockResolvedValue(new Response(JSON.stringify({
      items: [{ title: "Assurance level", status: "PASSWORD", detail: "Session assurance recorded at authentication.", source: "web_sessions.assurance_level" }],
      source: "identity_security_stores",
    }), { status: 200 }));
    const Parent = () => <Outlet context={session} />;
    render(<MemoryRouter initialEntries={["/dashboard/security"]}><Routes><Route element={<Parent />}><Route path="/dashboard/:domain" element={<DomainPage />} /></Route></Routes></MemoryRouter>);
    expect(await screen.findByText("PASSWORD")).toBeInTheDocument();
    expect(screen.getByText(/web_sessions.assurance_level/i)).toBeInTheDocument();
  });

  it("renders canonical approval quorum, vote history, purpose, and safe argument summary", async () => {
    vi.spyOn(window, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ approval_id: "appr-detail", action_type: "payment.send", target: "vendor" }], source: "approval_repository" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(approvalDetail({ approval_id: "appr-detail", action_type: "payment.send", target: "vendor", required_approvals: 2, current_vote_count: 1, purpose: "pay approved invoice", votes: [{ vote_id: "vote-1", resolver_identity_id: "internal-reviewer-7", outcome: "APPROVED", resolved_at: "2026-09-21T00:01:00Z" }] })), { status: 200 }));
    const Parent = () => <Outlet context={session} />;
    render(<MemoryRouter initialEntries={["/dashboard/approvals"]}><Routes><Route element={<Parent />}><Route path="/dashboard/:domain" element={<DomainPage />} /></Route></Routes></MemoryRouter>);
    expect(await screen.findByText("1 of 2 approvals")).toBeInTheDocument();
    expect(screen.getByText("pay approved invoice")).toBeInTheDocument();
    expect(screen.getByText(/1 arguments: amount/i)).toBeInTheDocument();
    expect(screen.getByText(/Authorized reviewer internal-reviewer-7/i)).toBeInTheDocument();
  });

  it("uses canonical evidence detail, verification, and unsigned attestation contracts", async () => {
    const record = { evidence_id: "ev-1", agent_id: "agent-1", action_type: "payment.send", target: "vendor", decision: "ALLOW", integrity_status: "CHAINED", recorded_at: "2026-09-21T00:00:00Z", hash: "hash-1" };
    vi.spyOn(window, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/verify")) return new Response(JSON.stringify({ org_id: "org-1", status: "INCOMPLETE", chain_intact: true, cryptographically_signed: false, integrity_note: "Legacy pre-canonical entries remain." }), { status: 200 });
      if (url.endsWith("/attestation")) return new Response(JSON.stringify({ evidence_id: "ev-1", action_id: "act-1", decision: "ALLOW", outcome_status: "UNKNOWN", reconciliation_status: "RECONCILED", evidence_hash: "hash-1", attested_at: "2026-09-21T00:02:00Z", cryptographically_signed: false, integrity_note: "Not cryptographically signed." }), { status: 200 });
      return new Response(JSON.stringify(record), { status: 200 });
    });
    const user = userEvent.setup();
    render(<MemoryRouter><EvidenceContractPanel records={[record]} /></MemoryRouter>);
    expect(await screen.findByText("INCOMPLETE")).toBeInTheDocument();
    expect(screen.getByText(/not presented as fully verified/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "View evidence" }));
    expect(await screen.findByRole("heading", { name: "Evidence details" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Evidence attestation" })).toBeInTheDocument();
    expect(screen.getByText("Reconciliation required")).toBeInTheDocument();
    expect(screen.getByText(/Not cryptographically signed/i)).toBeInTheDocument();
  });

  it("surfaces missing evidence detail without inventing an attestation", async () => {
    vi.spyOn(window, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "Evidence record not found." }), { status: 404 }));
    render(<MemoryRouter initialEntries={["/dashboard/evidence?evidence=missing"]}><EvidenceContractPanel records={[]} /></MemoryRouter>);
    expect(await screen.findByRole("alert")).toHaveTextContent("Request failed (404)");
    expect(screen.queryByRole("heading", { name: "Evidence attestation" })).not.toBeInTheDocument();
  });

  it("approves and denies pending requests through backend endpoints", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(window, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({
        items: [{ approval_id: "appr-1", action_type: "test.counter.increment", target: "test.counter.increment", risk_tier: "HIGH", status: "PENDING", requested_at: "2026-09-21T00:00:00Z", requested_by: "key-1" }],
        source: "approval_repository",
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(approvalDetail()), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "APPROVED" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(approvalDetail({ status: "APPROVED", current_vote_count: 1, votes: [{ vote_id: "v1", resolver_identity_id: "reviewer-1", outcome: "APPROVED", resolved_at: "2026-09-21T00:01:00Z" }] })), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ approval_id: "appr-1", execution_status: "SUCCEEDED", reconciliation_required: false, evidence_id: "ev-1", outcome_id: "out-1", message: "Execution completed with a known outcome." }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [] , source: "approval_repository" }), { status: 200 }));
    const Parent = () => <Outlet context={session} />;
    render(<MemoryRouter initialEntries={["/dashboard/approvals"]}><Routes><Route element={<Parent />}><Route path="/dashboard/:domain" element={<DomainPage />} /></Route></Routes></MemoryRouter>);
    expect(await screen.findByRole("button", { name: "Approve" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Approve" }));
    await user.click(screen.getByRole("button", { name: "Confirm approved" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/v1/web/approvals/appr-1/resolve", expect.objectContaining({ method: "POST" })));
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/web/approvals/appr-1/execute", expect.objectContaining({ method: "POST" }));
  });

  it("denies pending requests through the resolve endpoint without executing", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(window, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({
        items: [{ approval_id: "appr-2", action_type: "test.counter.increment", target: "test.counter.increment", risk_tier: "HIGH", status: "PENDING", requested_at: "2026-09-21T00:00:00Z", requested_by: "key-1" }],
        source: "approval_repository",
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(approvalDetail({ approval_id: "appr-2" })), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "DENIED" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(approvalDetail({ approval_id: "appr-2", status: "DENIED", denied_vote_count: 1, votes: [{ vote_id: "v2", resolver_identity_id: "reviewer-1", outcome: "DENIED", resolved_at: "2026-09-21T00:01:00Z" }] })), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [] , source: "approval_repository" }), { status: 200 }));
    const Parent = () => <Outlet context={session} />;
    render(<MemoryRouter initialEntries={["/dashboard/approvals"]}><Routes><Route element={<Parent />}><Route path="/dashboard/:domain" element={<DomainPage />} /></Route></Routes></MemoryRouter>);
    expect(await screen.findByRole("button", { name: "Deny" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Deny" }));
    await user.click(screen.getByRole("button", { name: "Confirm denied" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/v1/web/approvals/appr-2/resolve", expect.objectContaining({ method: "POST" })));
    expect(fetchMock).not.toHaveBeenCalledWith("/api/v1/web/approvals/appr-2/execute", expect.anything());
  });

  it("never presents an UNKNOWN execution outcome as success or retries it", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(window, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ approval_id: "appr-u", action_type: "external.send", target: "https://example.com", risk_tier: "HIGH", status: "PENDING", required_approvals: 1 }], source: "approval_repository" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(approvalDetail({ approval_id: "appr-u", action_type: "external.send", target: "https://example.com" })), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "APPROVED" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(approvalDetail({ approval_id: "appr-u", status: "APPROVED", current_vote_count: 1, votes: [{ vote_id: "v1", resolver_identity_id: "reviewer-1", outcome: "APPROVED", resolved_at: "2026-09-21T00:01:00Z" }] })), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ approval_id: "appr-u", execution_status: "UNKNOWN", reconciliation_required: true, evidence_id: "ev-u", outcome_id: "out-u", message: "The mutation may have applied; acknowledgement was lost. WhitePact will not retry automatically." }), { status: 200 }));
    const Parent = () => <Outlet context={session} />;
    render(<MemoryRouter initialEntries={["/dashboard/approvals"]}><Routes><Route element={<Parent />}><Route path="/dashboard/:domain" element={<DomainPage />} /></Route></Routes></MemoryRouter>);
    await user.click(await screen.findByRole("button", { name: "Approve" }));
    await user.click(screen.getByRole("button", { name: "Confirm approved" }));
    expect(await screen.findByRole("heading", { name: "Execution outcome is uncertain" })).toBeInTheDocument();
    expect(screen.queryByText(/execution acknowledged/i)).not.toBeInTheDocument();
    expect(screen.getByText("Reconciliation required")).toBeInTheDocument();
    expect(screen.getByText(/ev-u/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(5);
  });

  it.each([[409,"Approval is stale"],[403,"Not authorized"]])("surfaces approval HTTP %s without execution retry", async (status, detail) => {
    const user=userEvent.setup();
    const fetchMock=vi.spyOn(window,"fetch").mockResolvedValueOnce(new Response(JSON.stringify({items:[{approval_id:`appr-${status}`,action_type:"tool.call",target:"tool",status:"PENDING"}],source:"approval_repository"}),{status:200})).mockResolvedValueOnce(new Response(JSON.stringify(approvalDetail({approval_id:`appr-${status}`,action_type:"tool.call",target:"tool"})),{status:200})).mockResolvedValueOnce(new Response(JSON.stringify({detail}),{status}));
    const Parent=()=> <Outlet context={session}/>;
    render(<MemoryRouter initialEntries={["/dashboard/approvals"]}><Routes><Route element={<Parent/>}><Route path="/dashboard/:domain" element={<DomainPage/>}/></Route></Routes></MemoryRouter>);
    await user.click(await screen.findByRole("button",{name:"Approve"})); await user.click(screen.getByRole("button",{name:"Confirm approved"}));
    expect(await screen.findByRole("heading", { name: "Request could not be completed" })).toBeInTheDocument();
    expect(screen.getByText(detail)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("surfaces an approval network failure without executing", async () => {
    const user=userEvent.setup(); const fetchMock=vi.spyOn(window,"fetch").mockResolvedValueOnce(new Response(JSON.stringify({items:[{approval_id:"appr-net",action_type:"tool.call",target:"tool",status:"PENDING"}],source:"approval_repository"}),{status:200})).mockResolvedValueOnce(new Response(JSON.stringify(approvalDetail({approval_id:"appr-net",action_type:"tool.call",target:"tool"})),{status:200})).mockRejectedValueOnce(new TypeError("Network unavailable"));
    const Parent=()=> <Outlet context={session}/>; render(<MemoryRouter initialEntries={["/dashboard/approvals"]}><Routes><Route element={<Parent/>}><Route path="/dashboard/:domain" element={<DomainPage/>}/></Route></Routes></MemoryRouter>);
    await user.click(await screen.findByRole("button",{name:"Approve"})); await user.click(screen.getByRole("button",{name:"Confirm approved"}));
    expect(await screen.findByRole("heading", { name: "Request could not be completed" })).toBeInTheDocument(); expect(screen.getByText("Network unavailable")).toBeInTheDocument(); expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("collects onboarding data through all three steps", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "fetch").mockResolvedValue(new Response(JSON.stringify({ next: "/dashboard" }), { status: 200 }));
    render(<MemoryRouter><OnboardingPage /></MemoryRouter>);
    await user.type(screen.getByLabelText("Organization name"), "Analytical Engines");
    await user.selectOptions(screen.getByLabelText("Your role"), "Founder");
    await user.click(screen.getByRole("button", { name: /Continue/i }));
    await user.click(screen.getByLabelText("Agent development"));
    await user.click(screen.getByRole("button", { name: /Continue/i }));
    expect(screen.getByLabelText(/Community/i)).toBeChecked();
    await user.click(screen.getByRole("button", { name: /Create workspace/i }));
    await waitFor(() => expect(window.fetch).toHaveBeenCalledTimes(1));
  });
});
