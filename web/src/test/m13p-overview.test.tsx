// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { OverviewPage } from "../features/dashboard/OverviewPage";

const empty = { decisions: 0, agents: 0, pending_approvals: 0, blocked_actions: 0, recent_governance: [], services: {} };
function overview() {
  const Parent = () => <Outlet context={{ user: { full_name: "Ada" }, organization: { name: "Workspace" } }} />;
  return <MemoryRouter><Routes><Route element={<Parent />}><Route index element={<OverviewPage />} /></Route></Routes></MemoryRouter>;
}
afterEach(() => vi.restoreAllMocks());

it.each([null, {}, { ...empty, agents: -1 }, { ...empty, decisions: "0" }, { ...empty, recent_governance: [null] }, { ...empty, services: { MCP: true } }])("reports an unconfirmed summary instead of successful empty activity: %j", async (payload) => {
  const fetch = vi.spyOn(window, "fetch").mockResolvedValue(Response.json(payload));
  render(overview());
  expect(await screen.findByRole("alert")).toHaveTextContent("Governance summary could not be confirmed");
  expect(screen.queryByText("No governed activity yet")).not.toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Persisted governance summary" })).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(1);
});

it("recovers an invalid read only after explicit retry and preserves unknown backend labels", async () => {
  const fetch = vi.spyOn(window, "fetch").mockResolvedValueOnce(Response.json(null)).mockResolvedValueOnce(Response.json({
    ...empty, decisions: 1, agents: 1,
    recent_governance: [{ id: "e1", agent: "agent", action: "tool", policy: "v1", risk: "FUTURE_RISK", decision: "FUTURE_DECISION", timestamp: "reported timestamp" }],
    services: { MCP: "future status" },
  }));
  render(overview());
  await userEvent.click(await screen.findByRole("button", { name: "Retry" }));
  expect(await screen.findByText("FUTURE_DECISION")).toBeInTheDocument();
  expect(screen.getByText("FUTURE_RISK")).toBeInTheDocument();
  expect(screen.getByText("future status")).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(2);
});
