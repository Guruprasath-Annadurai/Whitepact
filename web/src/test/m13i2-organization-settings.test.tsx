// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { DomainPage } from "../features/dashboard/DomainPage";
import { OrganizationSettingsPage } from "../features/dashboard/OrganizationSettingsPage";

afterEach(() => vi.restoreAllMocks());
const snapshot = (id = "org-a", name = "Original organization") => ({ items: [{ id, name, slug: "workspace", plan: "FREE" }], source: "organization_repository", domain: "organization" });
// Explicit internal preparation seam only. The actual production route below
// never passes a verified-contract override and cannot submit a rename.
function page(id = "org-a", role = "OWNER", preparation = true) {
  const session = { user: { full_name: "Current user", email: "owner@example.com" }, organization: { id, name: "Session snapshot", plan: "FREE", role } };
  return <MemoryRouter><Routes><Route element={<Outlet context={session} />}><Route index element={preparation ? <OrganizationSettingsPage key={`${id}:${session.user.email}`} session={session} renameContractVerified /> : <DomainPage domainKey="organization" />} /></Route></Routes></MemoryRouter>;
}
async function changeName(name = "Renamed organization") {
  const input = await screen.findByRole("textbox", { name: "Organization name" });
  fireEvent.change(input, { target: { value: name } });
  fireEvent.click(screen.getByRole("button", { name: "Save organization" }));
}

it("keeps the actual organization route read-only even for an owner and never submits PATCH", async () => {
  const fetch = vi.spyOn(window, "fetch").mockResolvedValue(Response.json(snapshot()));
  render(page("org-a", "OWNER", false));
  expect(await screen.findByText("Original organization")).toBeInTheDocument();
  expect(screen.getByText("Organization name changes are unavailable pending workspace confirmation.")).toBeInTheDocument();
  expect(screen.queryByRole("form")).not.toBeInTheDocument();
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Save organization" })).not.toBeInTheDocument();
  expect(fetch.mock.calls.every(([, init]) => (init?.method ?? "GET") === "GET")).toBe(true);
  expect(fetch).toHaveBeenCalledTimes(1);
});

it("requires a semantically valid acknowledgement and a current GET before reporting rename success", async () => {
  let resolveRead!: (response: Response) => void;
  const fetch = vi.spyOn(window, "fetch").mockResolvedValueOnce(Response.json(snapshot())).mockResolvedValueOnce(Response.json({ id: "org-a", name: "Renamed organization" })).mockReturnValueOnce(new Promise((resolve) => { resolveRead = resolve; }));
  render(page()); await changeName("  Renamed organization  ");
  await screen.findByText("Checking the current server name…");
  expect(screen.queryByText(/name confirmed/)).not.toBeInTheDocument();
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  await act(async () => { resolveRead(Response.json(snapshot("org-a", "Renamed organization"))); });
  expect(await screen.findByRole("status")).toHaveTextContent("confirmed by the current server read");
  expect(screen.getByRole("textbox")).toHaveValue("Renamed organization");
  const [, request] = fetch.mock.calls[1];
  expect(request?.method).toBe("PATCH");
  expect(JSON.parse(String(request?.body))).toEqual({ name: "Renamed organization" });
  expect(fetch.mock.calls.map(([url]) => String(url))).toEqual(["/api/v1/web/dashboard/organization", "/api/v1/web/organization", "/api/v1/web/dashboard/organization"]);
});

it("prevents duplicate submissions while the PATCH is in flight", async () => {
  const fetch = vi.spyOn(window, "fetch").mockResolvedValueOnce(Response.json(snapshot())).mockReturnValueOnce(new Promise(() => {}));
  render(page());
  const form = await screen.findByRole("form", { name: "Organization name" });
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Renamed organization" } });
  act(() => { fireEvent.submit(form); fireEvent.submit(form); });
  expect(screen.getByRole("status")).toHaveTextContent("Submitting organization name change");
  expect(fetch.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(1);
  expect(screen.queryByRole("button", { name: "Save organization" })).not.toBeInTheDocument();
});

it.each([{}, { id: "other-org", name: "Renamed organization" }, { id: "org-a", name: "Different name" }])("keeps malformed/mismatched PATCH success uncertain until a manual GET", async (ack) => {
  const fetch = vi.spyOn(window, "fetch").mockResolvedValueOnce(Response.json(snapshot())).mockResolvedValueOnce(Response.json(ack)).mockResolvedValueOnce(Response.json(snapshot("org-a", "Server current name")));
  render(page()); await changeName();
  expect(await screen.findByRole("alert")).toHaveTextContent("may have completed");
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(2);
  fireEvent.click(screen.getByRole("button", { name: "Check current organization name" }));
  expect(await screen.findByRole("textbox")).toHaveValue("Server current name");
  expect(screen.getByRole("status")).toHaveTextContent("earlier rename outcome was not confirmed");
  expect(fetch.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(1);
});

it("does not retry a lost PATCH acknowledgement and remains locked when reconciliation fails", async () => {
  const fetch = vi.spyOn(window, "fetch").mockResolvedValueOnce(Response.json(snapshot())).mockRejectedValueOnce(new TypeError("response lost")).mockRejectedValueOnce(new TypeError("read unavailable"));
  render(page()); await changeName();
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Check current organization name" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("current organization name could not be confirmed");
  expect(screen.getByRole("button", { name: "Check current organization name" })).toBeInTheDocument();
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  expect(fetch.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(1);
});

it("does not infer rename success when the acknowledged name differs from a fresh read", async () => {
  vi.spyOn(window, "fetch").mockResolvedValueOnce(Response.json(snapshot())).mockResolvedValueOnce(Response.json({ id: "org-a", name: "Renamed organization" })).mockResolvedValueOnce(Response.json(snapshot("org-a", "Someone else's update")));
  render(page()); await changeName();
  expect(await screen.findByRole("alert")).toHaveTextContent("No rename success is claimed");
  expect(screen.getByRole("textbox")).toHaveValue("Someone else's update");
  expect(screen.queryByText(/name confirmed by/)).not.toBeInTheDocument();
});

it("keeps a valid PATCH acknowledgement uncertain when the required fresh read fails", async () => {
  const fetch = vi.spyOn(window, "fetch").mockResolvedValueOnce(Response.json(snapshot())).mockResolvedValueOnce(Response.json({ id: "org-a", name: "Renamed organization" })).mockRejectedValueOnce(new TypeError("read failed"));
  render(page()); await changeName();
  expect(await screen.findByRole("alert")).toHaveTextContent("current organization name could not be confirmed");
  expect(screen.getByRole("button", { name: "Check current organization name" })).toBeInTheDocument();
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  expect(screen.queryByText(/name confirmed by/)).not.toBeInTheDocument();
  expect(fetch.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(1);
});

it("does not apply a previous tenant's late PATCH acknowledgement or reconcile it in a new tenant", async () => {
  let resolve!: (response: Response) => void;
  const fetch = vi.spyOn(window, "fetch").mockResolvedValueOnce(Response.json(snapshot())).mockReturnValueOnce(new Promise((done) => { resolve = done; })).mockResolvedValueOnce(Response.json(snapshot("org-b", "Other workspace")));
  const { rerender } = render(page()); await changeName();
  expect(screen.getByRole("status")).toHaveTextContent("Submitting");
  rerender(page("org-b"));
  expect(await screen.findByRole("textbox")).toHaveValue("Other workspace");
  await act(async () => { resolve(Response.json({ id: "org-a", name: "Renamed organization" })); });
  expect(screen.getByRole("textbox")).toHaveValue("Other workspace");
  expect(fetch).toHaveBeenCalledTimes(3);
  expect(screen.queryByText(/name confirmed by/)).not.toBeInTheDocument();
});

it("keeps refused PATCH responses distinct from an uncertain acknowledgement", async () => {
  const fetch = vi.spyOn(window, "fetch").mockResolvedValueOnce(Response.json(snapshot())).mockResolvedValueOnce(Response.json({}, { status: 403 }));
  render(page()); await changeName();
  expect(await screen.findByRole("alert")).toHaveTextContent("server rejected");
  expect(screen.getByRole("button", { name: "Retry organization read" })).toBeInTheDocument();
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Check current organization name" })).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(2);
});

it("rejects an initial wrong-tenant snapshot instead of enabling an edit", async () => {
  vi.spyOn(window, "fetch").mockResolvedValue(Response.json(snapshot("other-org")));
  render(page());
  expect(await screen.findByRole("alert")).toHaveTextContent("could not be confirmed");
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Retry organization read" })).toBeInTheDocument();
});

it("aborts a tenant's pending read and ignores late results after a tenant switch", async () => {
  let resolve!: (response: Response) => void;
  const fetch = vi.spyOn(window, "fetch").mockReturnValueOnce(new Promise((done) => { resolve = done; })).mockResolvedValueOnce(Response.json(snapshot("org-b", "Other workspace")));
  const { rerender } = render(page());
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
  const signal = fetch.mock.calls[0][1]?.signal;
  rerender(page("org-b"));
  expect(signal?.aborted).toBe(true);
  expect(await screen.findByRole("textbox")).toHaveValue("Other workspace");
  await act(async () => { resolve(Response.json(snapshot())); });
  expect(screen.getByRole("textbox")).toHaveValue("Other workspace");
});

it("does not label the signed-in person as organization owner or expose save to a viewer", async () => {
  vi.spyOn(window, "fetch").mockResolvedValue(Response.json(snapshot()));
  render(page("org-a", "VIEWER"));
  expect(await screen.findByRole("textbox")).toHaveAttribute("readonly");
  expect(screen.queryByRole("button", { name: "Save organization" })).not.toBeInTheDocument();
  expect(screen.getByText("Signed-in user")).toBeInTheDocument();
  expect(screen.queryByText("Owner", { exact: true })).not.toBeInTheDocument();
});
