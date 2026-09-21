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

const session: WebSession = {
  user: { full_name: "Ada Lovelace", email: "ada@example.com" },
  organization: { id: "org-1", name: "Analytical Engines", plan: "FREE" },
};

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

  it("approves and denies pending requests through backend endpoints", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(window, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({
        items: [{ approval_id: "appr-1", action_type: "test.counter.increment", target: "test.counter.increment", risk_tier: "HIGH", status: "PENDING", requested_at: "2026-09-21T00:00:00Z", requested_by: "key-1" }],
        source: "approval_repository",
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "APPROVED" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ approval_id: "appr-1", result: { ok: true } }), { status: 200 }))
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
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "DENIED" }), { status: 200 }))
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
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "APPROVED" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ approval_id: "appr-u", error: "governance_unknown_outcome", message: "The mutation may have applied; acknowledgement was lost." }), { status: 200 }));
    const Parent = () => <Outlet context={session} />;
    render(<MemoryRouter initialEntries={["/dashboard/approvals"]}><Routes><Route element={<Parent />}><Route path="/dashboard/:domain" element={<DomainPage />} /></Route></Routes></MemoryRouter>);
    await user.click(await screen.findByRole("button", { name: "Approve" }));
    await user.click(screen.getByRole("button", { name: "Confirm approved" }));
    expect(await screen.findByRole("heading", { name: "Execution outcome is uncertain" })).toBeInTheDocument();
    expect(screen.queryByText(/execution acknowledged/i)).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it.each([[409,"Approval is stale"],[403,"Not authorized"]])("surfaces approval HTTP %s without execution retry", async (status, detail) => {
    const user=userEvent.setup();
    const fetchMock=vi.spyOn(window,"fetch").mockResolvedValueOnce(new Response(JSON.stringify({items:[{approval_id:`appr-${status}`,action_type:"tool.call",target:"tool",status:"PENDING"}],source:"approval_repository"}),{status:200})).mockResolvedValueOnce(new Response(JSON.stringify({detail}),{status}));
    const Parent=()=> <Outlet context={session}/>;
    render(<MemoryRouter initialEntries={["/dashboard/approvals"]}><Routes><Route element={<Parent/>}><Route path="/dashboard/:domain" element={<DomainPage/>}/></Route></Routes></MemoryRouter>);
    await user.click(await screen.findByRole("button",{name:"Approve"})); await user.click(screen.getByRole("button",{name:"Confirm approved"}));
    expect(await screen.findByRole("heading", { name: "Request could not be completed" })).toBeInTheDocument();
    expect(screen.getByText(detail)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("surfaces an approval network failure without executing", async () => {
    const user=userEvent.setup(); const fetchMock=vi.spyOn(window,"fetch").mockResolvedValueOnce(new Response(JSON.stringify({items:[{approval_id:"appr-net",action_type:"tool.call",target:"tool",status:"PENDING"}],source:"approval_repository"}),{status:200})).mockRejectedValueOnce(new TypeError("Network unavailable"));
    const Parent=()=> <Outlet context={session}/>; render(<MemoryRouter initialEntries={["/dashboard/approvals"]}><Routes><Route element={<Parent/>}><Route path="/dashboard/:domain" element={<DomainPage/>}/></Route></Routes></MemoryRouter>);
    await user.click(await screen.findByRole("button",{name:"Approve"})); await user.click(screen.getByRole("button",{name:"Confirm approved"}));
    expect(await screen.findByRole("heading", { name: "Request could not be completed" })).toBeInTheDocument(); expect(screen.getByText("Network unavailable")).toBeInTheDocument(); expect(fetchMock).toHaveBeenCalledTimes(2);
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
