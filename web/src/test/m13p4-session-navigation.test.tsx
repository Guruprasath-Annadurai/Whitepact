// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { DashboardShell } from "../features/dashboard/DashboardShell";
import { LoginPage } from "../features/auth/AuthPages";

const session = { user: { full_name: "Ada", email: "ada@example.invalid" }, organization: { id: "org", name: "Workspace", plan: "FREE" } };
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function shell() {
  render(<MemoryRouter initialEntries={["/dashboard"]}><Routes><Route path="/dashboard" element={<DashboardShell />}><Route index element={<main><h1>Workspace content</h1></main>} /></Route><Route path="/login" element={<LoginPage />} /><Route path="/" element={<p>Signed out destination</p>} /></Routes></MemoryRouter>);
}

it("announces an expired session and never mounts workspace content", async () => {
  const fetch = vi.spyOn(window, "fetch").mockResolvedValue(Response.json({}, { status: 401 }));
  shell();
  expect(await screen.findByText("Your session is no longer available. Sign in again to continue to your workspace.")).toHaveAttribute("role", "status");
  expect(screen.queryByRole("heading", { name: "Workspace content" })).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(1);
});

it.each(["disconnect", "malformed"])("hides workspace and avoids replay after %s logout acknowledgement", async (failure) => {
  const fetch = vi.spyOn(window, "fetch").mockImplementation(async (_url, init) => {
    if (init?.method === "POST") {
      if (failure === "disconnect") throw new TypeError("Disconnected");
      return Response.json({});
    }
    return Response.json(session);
  });
  shell();
  await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));
  expect(await screen.findByRole("heading", { name: "Sign out could not be confirmed" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Workspace content" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reload session" })).toBeInTheDocument();
  expect(fetch.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
});

it("leaves the workspace only after a canonical sign-out acknowledgement", async () => {
  vi.spyOn(window, "fetch").mockImplementation(async (_url, init) => Response.json(init?.method === "POST" ? { status: "signed_out" } : session));
  shell();
  await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));
  expect(await screen.findByText("Signed out destination")).toBeInTheDocument();
});

it("offers a keyboard skip target without changing route or issuing a second read", async () => {
  const fetch = vi.spyOn(window, "fetch").mockResolvedValue(Response.json(session));
  shell();
  const skip = await screen.findByRole("link", { name: "Skip to workspace content" });
  await userEvent.click(skip);
  expect(document.getElementById("workspace-content")).toHaveFocus();
  expect(fetch).toHaveBeenCalledTimes(1);
});

it("isolates the mobile drawer, traps keyboard focus and restores its opener on Escape", async () => {
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
  vi.spyOn(window, "fetch").mockResolvedValue(Response.json(session));
  shell();
  const user = userEvent.setup();
  const opener = await screen.findByRole("button", { name: "Open navigation" });
  expect(screen.queryByRole("navigation", { name: "Dashboard" })).not.toBeInTheDocument();
  expect(opener).toHaveAttribute("aria-expanded", "false");
  await user.click(opener);
  const dialog = screen.getByRole("dialog", { name: "Workspace navigation" });
  expect(dialog).toHaveAttribute("aria-modal", "true");
  expect(opener.closest(".dashboard-main")).toHaveAttribute("inert");
  await waitFor(() => expect(dialog.querySelector("a,button")).toHaveFocus());
  await user.tab({ shift: true });
  expect(screen.getByRole("button", { name: "Sign out" })).toHaveFocus();
  await user.keyboard("{Escape}");
  expect(opener).toHaveFocus();
  expect(opener).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
