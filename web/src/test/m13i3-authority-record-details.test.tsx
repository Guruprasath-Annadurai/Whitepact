// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { AuthorityRecordDetails } from "../features/authority/AuthorityRecordDetails";
import { readCustomerAuthorityRecords } from "../lib/customerAuthorityRecords";

afterEach(() => vi.restoreAllMocks());
const payload = () => ({ organization_id: "org-a", has_active_authority: true, revocation_epoch: 2,
  root_authority: { root_id: "root-1", subject_id: "subject-1", issuer: "Customer", root_type: "CUSTOMER", verification_method: "Recorded method", issued_at: "2025-01-01T00:00:00Z", expires_at: "2025-02-01T00:00:00Z", canonical_digest: "a".repeat(64), private_key: "UNEXPECTED-PRIVATE-FIELD" },
  consent_proof: { consent_id: "consent-1", scope_description: "Recorded local scope", purpose: "Recorded purpose", consent_method: "CRYPTOGRAPHIC_CEREMONY", allowed_action_types: ["local:read"], allowed_targets: Array.from({ length: 12 }, (_, index) => `local-target-${index}`), consented_at: "2025-01-01T00:00:00Z", canonical_digest: "b".repeat(64) } });
function page(id = "org-a") { const session = { user: { full_name: "Owner", email: "owner@example.com" }, organization: { id, name: id, plan: "FREE", role: "OWNER" } }; return <MemoryRouter><Routes><Route element={<Outlet context={session} />}><Route index element={<AuthorityRecordDetails key={id} />} /></Route></Routes></MemoryRouter>; }
function read() { fireEvent.click(screen.getByRole("button", { name: "Read recorded consent details" })); }

it("requires an explicit keyboard GET and renders literal recorded metadata without permission claims", async () => {
  const fetch = vi.spyOn(window, "fetch").mockResolvedValue(Response.json(payload()));
  render(page());
  expect(fetch).not.toHaveBeenCalled();
  const user = userEvent.setup(); await user.tab(); await user.keyboard("{Enter}");
  expect(await screen.findByText("Recorded local scope")).toBeInTheDocument();
  expect(screen.getByText("2025-02-01T00:00:00Z")).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("does not establish authority");
  expect(screen.queryByText("UNEXPECTED-PRIVATE-FIELD")).not.toBeInTheDocument();
  expect(within(screen.getByRole("list", { name: "Recorded consent targets" })).getAllByRole("listitem")).toHaveLength(10);
  expect(screen.getByText(/10 of 12 returned entries/)).toBeInTheDocument();
  expect(fetch.mock.calls[0][0]).toBe("/api/enterprise/organizations/org-a/authority/status");
  expect(fetch.mock.calls[0][1]?.method ?? "GET").toBe("GET");
  expect(fetch.mock.calls[0][1]?.body).toBeUndefined();
});

it("distinguishes genuinely absent records from failed reads", async () => {
  vi.spyOn(window, "fetch").mockResolvedValue(Response.json({ organization_id: "org-a", has_active_authority: false, revocation_epoch: 0, root_authority: null, consent_proof: null }));
  render(page()); read();
  expect(await screen.findByText("No root record was returned.")).toBeInTheDocument();
  expect(screen.getByText("No consent record was returned.")).toBeInTheDocument();
});

it.each([401, 403, 503])("keeps HTTP%s distinct and permits only an explicit read retry", async (status) => {
  const fetch = vi.spyOn(window, "fetch").mockResolvedValueOnce(Response.json({}, { status })).mockResolvedValueOnce(Response.json(payload()));
  render(page()); read();
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent(status === 401 ? "session has expired" : status === 403 ? "cannot read" : "could not be confirmed");
  expect(screen.queryByText("No consent record was returned.")).not.toBeInTheDocument();
  if (status === 401) expect(within(alert).getByRole("link", { name: "Sign in again" })).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Retry detail read" }));
  expect(await screen.findByText("Recorded local scope")).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(2);
});

it("clears prior consent on a lost refresh without automatic retries", async () => {
  const fetch = vi.spyOn(window, "fetch").mockResolvedValueOnce(Response.json(payload())).mockRejectedValueOnce(new TypeError("lost"));
  render(page()); read(); await screen.findByText("Recorded local scope");
  fireEvent.click(screen.getByRole("button", { name: "Refresh recorded details" }));
  expect(screen.queryByText("Recorded local scope")).not.toBeInTheDocument();
  expect(await screen.findByRole("alert")).toHaveTextContent("No empty or valid consent state is inferred");
  expect(fetch).toHaveBeenCalledTimes(2);
});

it("aborts and ignores a slow result after tenant switching", async () => {
  let resolve!: (value: Response) => void;
  const fetch = vi.spyOn(window, "fetch").mockReturnValue(new Promise<Response>((done) => { resolve = done; }));
  const { rerender } = render(page()); read();
  const signal = fetch.mock.calls[0][1]?.signal;
  expect(screen.getByRole("button", { name: "Refresh recorded details" })).toBeDisabled();
  rerender(page("org-b")); expect(signal?.aborted).toBe(true);
  await act(async () => { resolve(Response.json(payload())); });
  expect(screen.queryByText("Recorded local scope")).not.toBeInTheDocument();
  expect(screen.getByText("No detail read has been requested.")).toBeInTheDocument();
});

it.each(["tenant", "digest", "timestamp", "targets", "missing consent"])("rejects malformed %s before rendering recorded scope", async (mode) => {
  const value = payload();
  if (mode === "tenant") value.organization_id = "other-org";
  if (mode === "digest") value.root_authority.canonical_digest = "not-a-digest";
  if (mode === "timestamp") value.root_authority.issued_at = "not-a-date";
  if (mode === "targets") (value.consent_proof.allowed_targets as unknown) = [null];
  if (mode === "missing consent") (value as unknown as { consent_proof: null }).consent_proof = null;
  vi.spyOn(window, "fetch").mockResolvedValue(Response.json(value));
  await expect(readCustomerAuthorityRecords("org-a")).rejects.toThrow();
});
