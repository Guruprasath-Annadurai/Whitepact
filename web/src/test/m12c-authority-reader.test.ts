// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { afterEach, expect, it, vi } from "vitest";
import { customerAuthorityReader } from "../lib/customerAuthorityReader";
import { ApiError } from "../lib/api";

afterEach(() => vi.restoreAllMocks());
const session = { organization: { id: "server-org" } };
const active = { organization_id: "server-org", has_active_authority: true, root_authority: { root_id: "root-1" }, consent_proof: { consent_id: "consent-1" }, revocation_epoch: 1 };
const agent = { organization_id: "server-org", agent_id: "agent-1", display_name: "Registered agent", lifecycle_state: "ACTIVE", has_active_delegation: false };

it("prepares only session-authenticated GET status and inventory reads, without tenant payload or authority methods", async () => {
  const fetch = vi.spyOn(window, "fetch").mockImplementation(async (url) => Response.json(String(url).endsWith("status") ? active : { agents: [agent] }));
  const reader = customerAuthorityReader(session);
  expect(Object.keys(reader)).toEqual(["status", "agents"]);
  expect(await reader.status()).toEqual({ reportedActive: true, rootId: "root-1", consentId: "consent-1", epoch: 1 });
  expect(await reader.agents()).toEqual([{ id: "agent-1", displayName: "Registered agent", lifecycleState: "ACTIVE", reportedActiveDelegation: false }]);
  for (const [url, init] of fetch.mock.calls) {
    expect(String(url)).toMatch(/^\/api\/enterprise\/organizations\/server-org\/authority\/(status|agents)$/);
    expect(init?.credentials).toBe("same-origin");
    expect(init?.body).toBeUndefined();
    expect(init?.method ?? "GET").toBe("GET");
  }
});

it.each(["", ".", "..", "other/path", "org?override", "org%2fother", "org\nother", "\ud800"])("rejects malformed session context before dispatch: %j", (id) => {
  const fetch = vi.spyOn(window, "fetch");
  expect(() => customerAuthorityReader({ organization: { id } })).toThrow("organization context");
  expect(fetch).not.toHaveBeenCalled();
});

it.each([null, {}, { ...active, organization_id: "another-org" }, { ...active, has_active_authority: "true" }, { ...active, root_authority: null }, { ...active, consent_proof: null }, { ...active, revocation_epoch: -1 }])("does not promote malformed status into authority: %j", async (payload) => {
  vi.spyOn(window, "fetch").mockResolvedValue(Response.json(payload));
  await expect(customerAuthorityReader(session).status()).rejects.toThrow("could not be confirmed");
});

it.each([401, 403, 404, 409, 503])("preserves HTTP %i failure instead of fabricating inactive state", async (status) => {
  vi.spyOn(window, "fetch").mockResolvedValue(Response.json({}, { status }));
  await expect(customerAuthorityReader(session).status()).rejects.toMatchObject({ status });
  await expect(customerAuthorityReader(session).agents()).rejects.toBeInstanceOf(ApiError);
});

it.each([{ agents: [agent, agent] }, { agents: [{ ...agent, organization_id: "another-org" }] }, { agents: [{ ...agent, has_active_delegation: "true" }] }, {}])("rejects misleading inventory: %j", async (payload) => {
  vi.spyOn(window, "fetch").mockResolvedValue(Response.json(payload));
  await expect(customerAuthorityReader(session).agents()).rejects.toThrow("could not be confirmed");
});

it("does not expose unexpected secrets from a successful read", async () => {
  vi.spyOn(window, "fetch").mockResolvedValue(Response.json({ ...active, root_signing_secret: "synthetic-secret" }));
  expect(JSON.stringify(await customerAuthorityReader(session).status())).not.toContain("synthetic-secret");
});

it("preserves an explicit inactive response without claiming a particular revocation reason", async () => {
  vi.spyOn(window, "fetch").mockResolvedValue(Response.json({ ...active, has_active_authority: false, root_authority: null, consent_proof: null }));
  expect(await customerAuthorityReader(session).status()).toEqual({ reportedActive: false, rootId: null, consentId: null, epoch: 1 });
});

it("propagates a lost read without inventing empty inventory or retrying", async () => {
  const fetch = vi.spyOn(window, "fetch").mockRejectedValue(new TypeError("Synthetic network failure"));
  await expect(customerAuthorityReader(session).agents()).rejects.toThrow("Synthetic network failure");
  expect(fetch).toHaveBeenCalledTimes(1);
});
