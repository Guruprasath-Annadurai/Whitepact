// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { DashboardShell } from "../features/dashboard/DashboardShell";
import { PolicyPage } from "../features/policy/PolicyPage";

afterEach(() => vi.restoreAllMocks());
const session = { user: { full_name: "Reviewer", email: "reviewer@example.invalid" }, organization: { id: "fixture", name: "Fixture", plan: "FREE", role: "OWNER" } };
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });

function shell() {
  render(<MemoryRouter initialEntries={["/dashboard"]}><Routes><Route path="/dashboard" element={<DashboardShell />}><Route index element={<p>Verified workspace</p>} /></Route><Route path="/login" element={<p>Login destination</p>} /></Routes></MemoryRouter>);
}
function policy() {
  const Parent = () => <Outlet context={session} />;
  render(<MemoryRouter><Routes><Route element={<Parent />}><Route path="/" element={<PolicyPage />} /></Route></Routes></MemoryRouter>);
}

it("does not call a provider outage an expired session; read-only retry recovers", async () => {
  vi.spyOn(window, "fetch").mockResolvedValueOnce(json({ detail: "sensitive provider detail" }, 503)).mockResolvedValueOnce(json(session));
  shell();
  expect(await screen.findByRole("heading", { name: "Session verification unavailable" })).toBeInTheDocument();
  expect(screen.queryByText("Login destination")).not.toBeInTheDocument();
  expect(screen.queryByText(/sensitive provider detail/)).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Retry session verification" }));
  expect(await screen.findByText("Verified workspace")).toBeInTheDocument();
});

it("reports forbidden session access without misclassifying it as unauthenticated", async () => {
  vi.spyOn(window, "fetch").mockResolvedValue(json({}, 403)); shell();
  expect(await screen.findByRole("heading", { name: "Workspace access unavailable" })).toBeInTheDocument();
  expect(screen.queryByText("Login destination")).not.toBeInTheDocument();
});

it("redirects an actual unauthenticated response to login", async () => {
  vi.spyOn(window, "fetch").mockResolvedValue(json({}, 401)); shell();
  expect(await screen.findByText("Login destination")).toBeInTheDocument();
});

it("rejects malformed HTTP-success session data without rendering an authenticated shell", async () => {
  vi.spyOn(window, "fetch").mockResolvedValue(json(null)); shell();
  expect(await screen.findByRole("heading", { name: "Session verification unavailable" })).toBeInTheDocument();
  expect(screen.queryByText("Verified workspace")).not.toBeInTheDocument();
});

it("respects canonical policy can_edit false even when the cached role says OWNER", async () => {
  vi.spyOn(window, "fetch").mockResolvedValue(json({ org_id: "fixture", rules: [], can_edit: false })); policy();
  expect(await screen.findByText("No rules configured yet.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Add rule/ })).not.toBeInTheDocument();
});

it("requires accessible confirmation before removing an ordered policy rule", async () => {
  const fetch = vi.spyOn(window, "fetch").mockImplementation(async (_url, init) => {
    if (init?.method === "DELETE") return json({ status: "removed", rule_id: "rule-one" });
    return json({ org_id: "fixture", rules: [{ rule_id: "rule-one", reason_code: "review", effect: "DENY" }], can_edit: true });
  }); policy();
  await userEvent.click(await screen.findByRole("button", { name: "Remove rule" }));
  expect(screen.getByRole("dialog", { name: "Remove policy rule?" })).toBeInTheDocument();
  expect(fetch.mock.calls.filter(([, init]) => init?.method === "DELETE")).toHaveLength(0);
  await userEvent.click(screen.getByRole("button", { name: "Confirm removal" }));
  await waitFor(() => expect(fetch.mock.calls.filter(([, init]) => init?.method === "DELETE")).toHaveLength(1));
});

it("locks policy mutations after a lost acknowledgement until canonical read reconciliation", async () => {
  const fetch = vi.spyOn(window, "fetch").mockImplementation(async (_url, init) => {
    if (init?.method === "POST") throw new TypeError("Failed to fetch");
    return json({ org_id: "fixture", rules: [], can_edit: true });
  }); policy();
  await screen.findByRole("button", { name: /Add rule/ });
  await userEvent.type(screen.getByRole("textbox", { name: "Rule ID" }), "rule-one");
  await userEvent.type(screen.getByRole("textbox", { name: "Reason code" }), "review");
  await userEvent.click(screen.getByRole("button", { name: /Add rule/ }));
  expect(await screen.findByRole("heading", { name: "Policy change outcome is uncertain" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Add rule/ })).toBeDisabled();
  expect(fetch.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
  await userEvent.click(screen.getByRole("button", { name: "Reload canonical policy" }));
  await waitFor(() => expect(screen.queryByRole("heading", { name: "Policy change outcome is uncertain" })).not.toBeInTheDocument());
  expect(fetch.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
});
