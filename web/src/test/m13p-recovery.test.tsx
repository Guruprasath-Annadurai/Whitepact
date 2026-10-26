// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { afterEach, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { readRecoveryRecords } from "../features/authority/recoveryReader";
import { RecoveryRecordsPreparation } from "../features/authority/RecoveryRecordsPreparation";

afterEach(() => vi.restoreAllMocks());
const session = { organization: { id: "org-session" } };
const record = { request_id: "req-1", organization_id: "org-session", request_type: "ROOT_RECOVERY", target_root_id: "root-1", requester_user_id: "user-1", status: "UNKNOWN_FUTURE", expires_at: "2026-10-16T00:00:00Z", required_quorum_m: 1, proposed_parameters: { secret: "do-not-copy" } };
it("uses only session addressing with no mutation, tenant payload or arbitrary parameters", async () => {
  const fetch = vi.spyOn(window, "fetch").mockResolvedValue(Response.json({ requests: [record] }));
  const records = await readRecoveryRecords(session);
  expect(records).toEqual([{ id: "req-1", type: "ROOT_RECOVERY", rootId: "root-1", requesterId: "user-1", status: "UNKNOWN_FUTURE", expiresAt: record.expires_at }]);
  const [url, init] = fetch.mock.calls[0];
  expect(url).toBe("/api/enterprise/organizations/org-session/authority/recovery/requests");
  expect(init?.body).toBeUndefined(); expect(init?.credentials).toBe("same-origin");
  expect(init?.method ?? "GET").toBe("GET");
  expect(JSON.stringify(records)).not.toContain("do-not-copy");
});
it.each([{}, { requests: [record, record] }, { requests: [{ ...record, organization_id: "other" }] }, { requests: [{ ...record, status: true }] }])("rejects malformed or cross-tenant data", async (payload) => {
  vi.spyOn(window, "fetch").mockResolvedValue(Response.json(payload));
  await expect(readRecoveryRecords(session)).rejects.toThrow("could not be confirmed");
});
it.each([401, 403, 404, 409, 503])("preserves HTTP %s instead of a successful empty read", async (status) => {
  const fetch = vi.spyOn(window, "fetch").mockResolvedValue(Response.json({}, { status }));
  await expect(readRecoveryRecords(session)).rejects.toMatchObject({ status });
  expect(fetch).toHaveBeenCalledTimes(1);
});
it("rejects invalid organization context before dispatch", async () => {
  const fetch = vi.spyOn(window, "fetch");
  await expect(readRecoveryRecords({ organization: { id: "../other" } })).rejects.toThrow("context is unavailable");
  expect(fetch).not.toHaveBeenCalled();
});
it("does not retry disconnects", async () => {
  const fetch = vi.spyOn(window, "fetch").mockRejectedValue(new TypeError("network"));
  await expect(readRecoveryRecords(session)).rejects.toThrow("network");
  expect(fetch).toHaveBeenCalledTimes(1);
});
it("renders unknown server labels without computing quorum or adding mutation controls", () => {
  render(<RecoveryRecordsPreparation state={{ kind: "ready", records: [{ id: "r".repeat(200), type: "ROOT_RECOVERY", rootId: "root-1", requesterId: "user-1", status: "UNKNOWN_FUTURE", expiresAt: "reported-date" }] }} />);
  expect(screen.getByText("UNKNOWN_FUTURE")).toBeInTheDocument();
  expect(screen.getByText(/No vote tally is computed here/)).toBeInTheDocument();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});
it.each(["unavailable", "loading", "error"] as const)("distinguishes %s from empty", (kind) => {
  render(<RecoveryRecordsPreparation state={{ kind }} />);
  expect(screen.getByRole(kind === "error" ? "alert" : "status")).toBeInTheDocument();
  expect(screen.queryByText(/No records were returned/)).not.toBeInTheDocument();
});
it("reports only an explicitly successful empty read as empty", () => {
  render(<RecoveryRecordsPreparation state={{ kind: "ready", records: [] }} />);
  expect(screen.getByRole("status")).toHaveTextContent("No records were returned by this read");
});
