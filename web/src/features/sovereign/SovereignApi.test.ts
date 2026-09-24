// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SovereignCapabilities } from "../../../../sdk/typescript/sovereign/types";
import contract from "../../../../contracts/sovereign-v1-web.json";
import { browserCapabilityState, sovereignOperations, SovereignWebApi, sovereignFixturesAllowed } from "./SovereignApi";

const capabilities: SovereignCapabilities = {
  sovereign_version: "1.0.0",
  protocol_version: "1.0.0",
  features: [
    { name: "status", availability: "AVAILABLE" },
    { name: "xray", availability: "AVAILABLE" },
    { name: "authority_bom", availability: "EXPERIMENTAL" },
    { name: "gauntlet", availability: "UNAVAILABLE" },
  ],
};

describe("Sovereign browser contract boundary", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("negotiates status and capabilities through the web-session route family", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ sovereign_version: "1.0.0", protocol_version: "1.0.0" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(capabilities), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const result = await new SovereignWebApi().negotiate();
    expect(result.capabilities.features).toHaveLength(4);
    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      "/api/web/sovereign/status",
      "/api/web/sovereign/capabilities",
    ]);
    expect(fetchMock.mock.calls.every(([, init]) => init.credentials === "same-origin")).toBe(true);
  });

  it("preserves canonical capability availability", () => {
    expect(browserCapabilityState(capabilities, "status")).toBe("AVAILABLE");
    expect(browserCapabilityState(capabilities, "xray")).toBe("AVAILABLE");
    expect(browserCapabilityState(capabilities, "authority_bom")).toBe("EXPERIMENTAL");
    expect(browserCapabilityState(capabilities, "gauntlet")).toBe("UNAVAILABLE");
    expect(browserCapabilityState(capabilities, "trace")).toBe("UNKNOWN");
  });

  it("forbids fixture data in production", () => {
    expect(sovereignFixturesAllowed(true)).toBe(true);
    expect(sovereignFixturesAllowed(false)).toBe(false);
  });

  it("matches every adapter path and method to the canonical browser contract", () => {
    const browserPaths = new Set(contract.capabilities.flatMap((capability) => capability.endpoints)
      .filter((endpoint) => endpoint.path.startsWith("/api/web/sovereign/"))
      .map((endpoint) => `${endpoint.method} ${endpoint.path}`));
    for (const operation of Object.values(sovereignOperations)) {
      expect(browserPaths.has(`POST ${operation.path}`)).toBe(true);
      expect(operation.zeroEffect).toBe(true);
    }
    expect(Object.values(sovereignOperations).some(({ path }) => path.includes("authority/expected"))).toBe(false);
    expect(Object.values(sovereignOperations).every(({ path }) => !path.startsWith("/api/sovereign/"))).toBe(true);
  });

  it("sends session credentials and CSRF while never injecting tenant identity", async () => {
    document.cookie = "wp_csrf=csrf-test; path=/";
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ disposition: "UNKNOWN" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const result = await new SovereignWebApi().execute("mission", { agent_id: "agent", steps: [] });
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(init.headers);
    expect(path).toBe("/api/web/sovereign/simulate/mission");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("same-origin");
    expect(headers.get("X-WP-CSRF")).toBe("csrf-test");
    expect(init.body).toBe(JSON.stringify({ agent_id: "agent", steps: [] }));
    expect(result.disposition).toBe("UNKNOWN");
  });

  it("rejects browser tenant authority in the request envelope", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    await expect(new SovereignWebApi().execute("compare", { organization_id: "forged", manifest: {} })).rejects.toThrow("derived from the authenticated session");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("preserves MISSING stages and Gauntlet statuses without fabricating PASS", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ stages: [{ status: "MISSING" }] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ cases: [{ status: "ERROR" }] }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    expect((await new SovereignWebApi().execute("trace", { evidence_id: "ev" })).stages).toEqual([{ status: "MISSING" }]);
    expect((await new SovereignWebApi().execute("gauntlet", {})).cases).toEqual([{ status: "ERROR" }]);
  });
});
