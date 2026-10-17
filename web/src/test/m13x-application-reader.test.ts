// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { afterEach, expect, it, vi } from "vitest";
import { customerApplicationReader } from "../lib/customerApplicationReader";

afterEach(() => vi.restoreAllMocks());
const session = { organization: { id: "server-org" } };
const app = {
  organization_id: "server-org",
  application_id: "app-1",
  name: "Customer Service App",
  description: "Handles customer support inquiries",
  environment: "production",
  lifecycle_state: "ACTIVE",
  has_execution_authority: false,
  agent_count: 2,
};
const capability = {
  organization_id: "server-org",
  capability_id: "cap-1",
  agent_id: "agent-1",
  application_id: "app-1",
  kind: "DELEGATED_ACTION",
  action_type: "DATABASE_READ",
  allowed_targets: ["db.customer.read"],
  status: "AUTHORIZED",
  requires_approval: false,
  requires_passkey_stepup: false,
  root_id: "root-1",
  delegation_id: "del-1",
  consent_id: "consent-1",
  authority_enforced: true,
};

it("reads application inventory with proper tenant scoping and execution authority enforcement", async () => {
  const fetch = vi.spyOn(window, "fetch").mockImplementation(async (url) => {
    if (String(url).endsWith("applications")) {
      return Response.json({ applications: [app] });
    }
    return Response.json({ capabilities: [capability] });
  });

  const reader = customerApplicationReader(session);
  const apps = await reader.applications();
  expect(apps).toEqual([
    {
      id: "app-1",
      name: "Customer Service App",
      description: "Handles customer support inquiries",
      environment: "production",
      lifecycleState: "ACTIVE",
      hasExecutionAuthority: false,
      agentCount: 2,
    },
  ]);

  const caps = await reader.capabilities();
  expect(caps).toEqual([
    {
      id: "cap-1",
      agentId: "agent-1",
      applicationId: "app-1",
      kind: "DELEGATED_ACTION",
      actionType: "DATABASE_READ",
      allowedTargets: ["db.customer.read"],
      status: "AUTHORIZED",
      requiresApproval: false,
      requiresPasskeyStepup: false,
      rootId: "root-1",
      delegationId: "del-1",
      consentId: "consent-1",
      authorityEnforced: true,
    },
  ]);

  for (const [url, init] of fetch.mock.calls) {
    expect(String(url)).toMatch(
      /^\/api\/enterprise\/organizations\/server-org\/authority\/(applications|capabilities)$/
    );
    expect(init?.credentials).toBe("same-origin");
    expect(init?.method ?? "GET").toBe("GET");
  }
});

it("rejects application inventory from another organization or claiming execution authority", async () => {
  vi.spyOn(window, "fetch").mockResolvedValueOnce(
    Response.json({ applications: [{ ...app, organization_id: "another-org" }] })
  );
  await expect(customerApplicationReader(session).applications()).rejects.toThrow(
    "could not be confirmed"
  );

  vi.spyOn(window, "fetch").mockResolvedValueOnce(
    Response.json({ applications: [{ ...app, has_execution_authority: true }] })
  );
  await expect(customerApplicationReader(session).applications()).rejects.toThrow(
    "could not be confirmed"
  );

  vi.spyOn(window, "fetch").mockResolvedValueOnce(
    Response.json({ applications: [{ ...app, agent_count: -1 }] })
  );
  await expect(customerApplicationReader(session).applications()).rejects.toThrow(
    "could not be confirmed"
  );
});

it("rejects capability inventory from another organization or missing authority provenance", async () => {
  vi.spyOn(window, "fetch").mockResolvedValueOnce(
    Response.json({ capabilities: [{ ...capability, organization_id: "another-org" }] })
  );
  await expect(customerApplicationReader(session).capabilities()).rejects.toThrow(
    "could not be confirmed"
  );

  for (const invalidCap of [
    { ...capability, authority_enforced: false },
    { ...capability, requires_approval: "false" },
    { ...capability, root_id: null },
    { ...capability, delegation_id: null },
    { ...capability, consent_id: null },
    { ...capability, allowed_targets: [] },
    { ...capability, status: "REVOKED", requires_approval: false },
  ]) {
    vi.spyOn(window, "fetch").mockResolvedValueOnce(
      Response.json({ capabilities: [invalidCap] })
    );
    await expect(customerApplicationReader(session).capabilities()).rejects.toThrow(
      "could not be confirmed"
    );
  }
});

it("rejects malformed agent identifier or mismatched agent_id on agent-scoped capabilities", async () => {
  const fetch = vi.spyOn(window, "fetch");
  await expect(
    customerApplicationReader(session).capabilities(undefined, "../other")
  ).rejects.toThrow("Agent identifier is invalid");
  expect(fetch).not.toHaveBeenCalled();

  vi.spyOn(window, "fetch").mockResolvedValueOnce(
    Response.json({ capabilities: [{ ...capability, agent_id: "agent-other" }] })
  );
  await expect(
    customerApplicationReader(session).capabilities(undefined, "agent-1")
  ).rejects.toThrow("could not be confirmed");
});

it.each(["", ".", "..", "other/path", "org?override", "org%2fother", "org\nother", "\ud800"])(
  "rejects malformed session context before dispatch: %j",
  (id) => {
    const fetch = vi.spyOn(window, "fetch");
    expect(() => customerApplicationReader({ organization: { id } })).toThrow(
      "organization context"
    );
    expect(fetch).not.toHaveBeenCalled();
  }
);
