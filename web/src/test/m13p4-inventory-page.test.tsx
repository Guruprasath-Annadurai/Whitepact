// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { AgentInventoryPage } from "../features/inventory/AgentInventoryPage";

afterEach(() => vi.restoreAllMocks());
const session = (id: string) => ({ user: { full_name: "Owner", email: "owner@example.com" }, organization: { id, name: id, plan: "FREE", role: "OWNER" } });
const record = (id: string) => ({ agent_id: `agent-${id}`, organization_id: id, display_name: `Agent in ${id}`, lifecycle_state: "UNKNOWN_FUTURE", has_active_delegation: true });
function page(id: string) {
  return <MemoryRouter><Routes><Route element={<Outlet context={session(id)} />}><Route index element={<AgentInventoryPage />} /></Route></Routes></MemoryRouter>;
}

it("keeps authority panel identities distinct across organization changes", async () => {
  const errors = vi.spyOn(console, "error");
  vi.spyOn(window, "fetch").mockImplementation(async () => Response.json({ agents: [] }));
  const { rerender } = render(page("org-a"));
  await screen.findByText(/No agent registrations were returned by this read/);
  rerender(page("org-b"));
  await screen.findByText(/No agent registrations were returned by this read/);
  expect(errors.mock.calls.filter((args) => args.some((value) => typeof value === "string" && /same key/.test(value)))).toEqual([]);
});

it("loads the actual session-addressed GET and renders only returned read fields", async () => {
  const fetch = vi.spyOn(window, "fetch").mockResolvedValue(Response.json({ agents: [record("org-a")] }));
  render(page("org-a"));
  expect(screen.getByRole("status")).toHaveTextContent("Loading");
  expect(await screen.findByRole("heading", { name: "Agent in org-a" })).toBeInTheDocument();
  expect(fetch.mock.calls[0][0]).toBe("/api/enterprise/organizations/org-a/authority/agents");
  expect(fetch.mock.calls[0][1]?.method ?? "GET").toBe("GET");
  expect(fetch.mock.calls[0][1]?.body).toBeUndefined();
  expect(screen.getByText("Reported active — not execution authority")).toBeInTheDocument();
  expect(screen.queryByText(/Integration preparation/)).not.toBeInTheDocument();
});

it("does not retry failures automatically; manual retry clears the failure and shows confirmed empty", async () => {
  const fetch = vi.spyOn(window, "fetch").mockResolvedValueOnce(Response.json({}, { status: 403 })).mockResolvedValueOnce(Response.json({ agents: [] }));
  render(page("org-a"));
  expect(await screen.findByText(/server did not permit this inventory read/)).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Retry inventory read" }));
  expect(await screen.findByText(/No agent registrations were returned by this read/)).toBeInTheDocument();
  expect(screen.queryByText(/server did not permit/)).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(2);
});

it("aborts old tenant reads and ignores late acknowledgements after organization change", async () => {
  let resolveOld!: (response: Response) => void;
  const old = new Promise<Response>((resolve) => { resolveOld = resolve; });
  const fetch = vi.spyOn(window, "fetch").mockReturnValueOnce(old).mockResolvedValueOnce(Response.json({ agents: [record("org-b")] }));
  const { rerender } = render(page("org-a"));
  const oldSignal = fetch.mock.calls[0][1]?.signal;
  rerender(page("org-b"));
  expect(oldSignal?.aborted).toBe(true);
  expect(await screen.findByRole("heading", { name: "Agent in org-b" })).toBeInTheDocument();
  resolveOld(Response.json({ agents: [record("org-a")] }));
  await waitFor(() => expect(screen.queryByRole("heading", { name: "Agent in org-a" })).not.toBeInTheDocument());
  expect(screen.getByRole("heading", { name: "Agent in org-b" })).toBeInTheDocument();
});

it("rejects a cross-tenant payload instead of displaying its registration", async () => {
  vi.spyOn(window, "fetch").mockResolvedValue(Response.json({ agents: [record("org-b")] }));
  render(page("org-a"));
  expect(await screen.findByRole("button", { name: "Retry inventory read" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Agent in org-b" })).not.toBeInTheDocument();
  expect(screen.queryByText(/No agent registrations were returned/)).not.toBeInTheDocument();
});

it("refreshes only on explicit request and removes an old successful list on a failed refresh", async () => {
  const fetch = vi.spyOn(window, "fetch").mockResolvedValueOnce(Response.json({ agents: [record("org-a")] })).mockRejectedValueOnce(new TypeError("connection lost"));
  render(page("org-a"));
  expect(screen.getByRole("region", { name: "Read-only agent inventory" })).toHaveAttribute("aria-busy", "true");
  expect(screen.getByRole("button", { name: "Refresh inventory read" })).toBeDisabled();
  await screen.findByRole("heading", { name: "Agent in org-a" });
  expect(fetch).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Refresh inventory read" }));
  expect(screen.queryByRole("heading", { name: "Agent in org-a" })).not.toBeInTheDocument();
  expect(await screen.findByRole("alert")).toHaveTextContent("No empty or successful result is claimed");
  expect(screen.getAllByRole("alert")).toHaveLength(1);
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(screen.getByRole("button", { name: "Retry inventory read" })).toBeInTheDocument();
});
