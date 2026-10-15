// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { AuthorityRecordStatus } from "../features/authority/AuthorityRecordStatus";

afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });
const response = (organization_id = "org-a", active = false) => ({ organization_id, has_active_authority: active, root_authority: active ? { root_id: "root-1" } : null, consent_proof: active ? { consent_id: "consent-1" } : null, revocation_epoch: 2 });
function page(id: string | null = "org-a") {
  const session = { user: { full_name: "Owner", email: "owner@example.com" }, organization: id ? { id, name: id, plan: "FREE", role: "OWNER" } : null };
  return <MemoryRouter><Routes><Route element={<Outlet context={session} />}><Route index element={<AuthorityRecordStatus key={id ?? "unavailable"} />} /></Route></Routes></MemoryRouter>;
}
function requestRead() { fireEvent.click(screen.getByRole("button", { name: "Read reported root and consent status" })); }

it("requests the supported GET only when explicitly requested and is keyboard operable", async () => {
  const fetch = vi.spyOn(window, "fetch").mockResolvedValue(Response.json(response()));
  const user = userEvent.setup();
  render(page());
  expect(fetch).not.toHaveBeenCalled();
  await user.tab();
  expect(screen.getByRole("button", { name: "Read reported root and consent status" })).toHaveFocus();
  await user.keyboard("{Enter}");
  expect(await screen.findByText(/backend did not report an active root and consent record pair/)).toBeInTheDocument();
  expect(fetch.mock.calls[0][0]).toBe("/api/enterprise/organizations/org-a/authority/status");
  expect(fetch.mock.calls[0][1]?.method ?? "GET").toBe("GET");
  expect(fetch.mock.calls[0][1]?.body).toBeUndefined();
  expect(fetch.mock.calls[0][1]?.credentials).toBe("same-origin");
  expect(screen.getByText("Reported revocation epoch").nextElementSibling).toHaveTextContent("2");
});

it("presents a reported record pair without capability, expiry or execution authorization inference", async () => {
  vi.spyOn(window, "fetch").mockResolvedValue(Response.json(response("org-a", true)));
  render(page()); requestRead();
  expect(await screen.findByText("root-1")).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("This is not execution authority");
  expect(screen.getByText(/not a live revocation guarantee/)).toBeInTheDocument();
  expect(screen.getByText(/Application ownership and executable capability inventory remain unavailable/)).toBeInTheDocument();
  expect(screen.getAllByRole("button")).toHaveLength(1);
});

it.each([401, 403, 503])("keeps HTTP %s distinct from inactive status with explicit retry", async (status) => {
  const fetch = vi.spyOn(window, "fetch").mockResolvedValueOnce(Response.json({}, { status })).mockResolvedValueOnce(Response.json(response()));
  render(page()); requestRead();
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent(status === 401 ? "session has expired" : status === 403 ? "cannot read" : "could not be confirmed");
  expect(screen.queryByText("Reported revocation epoch")).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(1);
  if (status === 401) expect(within(alert).getByRole("link", { name: "Sign in again" })).toHaveAttribute("href", "/login?next=%2Fdashboard%2Fagents");
  fireEvent.click(screen.getByRole("button", { name: "Retry status read" }));
  expect(await screen.findByText(/backend did not report an active root and consent record pair/)).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(2);
});

it("clears a prior successful snapshot when refresh fails, without automatic retry", async () => {
  const fetch = vi.spyOn(window, "fetch").mockResolvedValueOnce(Response.json(response("org-a", true))).mockRejectedValueOnce(new TypeError("lost read"));
  render(page()); requestRead();
  await screen.findByText("root-1");
  fireEvent.click(screen.getByRole("button", { name: "Refresh reported status" }));
  expect(screen.queryByText("root-1")).not.toBeInTheDocument();
  expect(await screen.findByRole("alert")).toHaveTextContent("No inactive or successful state is inferred");
  expect(fetch).toHaveBeenCalledTimes(2);
});

it("rejects cross-tenant and malformed success payloads", async () => {
  vi.spyOn(window, "fetch").mockResolvedValue(Response.json(response("other-org", true)));
  render(page()); requestRead();
  expect(await screen.findByRole("alert")).toHaveTextContent("could not be confirmed");
  expect(screen.queryByText("root-1")).not.toBeInTheDocument();
});

it("aborts a slow read, hides it immediately on tenant change and ignores its late response", async () => {
  let resolve!: (value: Response) => void;
  const fetch = vi.spyOn(window, "fetch").mockReturnValue(new Promise<Response>((done) => { resolve = done; }));
  const { rerender } = render(page()); requestRead();
  expect(screen.getByRole("region", { name: "Reported root and consent records" })).toHaveAttribute("aria-busy", "true");
  expect(screen.getByRole("button", { name: "Refresh reported status" })).toBeDisabled();
  const signal = fetch.mock.calls[0][1]?.signal;
  rerender(page("org-b"));
  expect(signal?.aborted).toBe(true);
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(screen.getByText("No record-status read has been requested.")).toBeInTheDocument();
  await act(async () => { resolve(Response.json(response("org-a", true))); });
  expect(screen.queryByText("root-1")).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(1);
});

it("turns the shared read timeout into unavailable status without retry or inactive claim", async () => {
  vi.useFakeTimers();
  const fetch = vi.spyOn(window, "fetch").mockImplementation((_path, init) => new Promise((_resolve, reject) => {
    init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
  }));
  render(page()); requestRead();
  await act(async () => { await vi.advanceTimersByTimeAsync(15_000); });
  expect(screen.getByRole("alert")).toHaveTextContent("could not be confirmed");
  expect(screen.queryByText("Reported revocation epoch")).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(1);
});

it("does not dispatch or expose controls when organization context is missing", () => {
  const fetch = vi.spyOn(window, "fetch");
  render(page(null));
  expect(screen.getByText(/No status read was submitted/)).toBeInTheDocument();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
});
