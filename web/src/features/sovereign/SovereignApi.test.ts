// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SovereignCapabilities } from "../../../../sdk/typescript/sovereign/types";
import { browserCapabilityState, SovereignWebApi, sovereignFixturesAllowed } from "./SovereignApi";

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

  it("uses canonical negotiation without treating Core availability as browser authorization", () => {
    expect(browserCapabilityState(capabilities, "status")).toBe("AVAILABLE");
    expect(browserCapabilityState(capabilities, "xray")).toBe("AUTH_CONTRACT_REQUIRED");
    expect(browserCapabilityState(capabilities, "authority_bom")).toBe("AUTH_CONTRACT_REQUIRED");
    expect(browserCapabilityState(capabilities, "gauntlet")).toBe("UNAVAILABLE");
    expect(browserCapabilityState(capabilities, "trace")).toBe("UNKNOWN");
  });

  it("forbids fixture data in production", () => {
    expect(sovereignFixturesAllowed(true)).toBe(true);
    expect(sovereignFixturesAllowed(false)).toBe(false);
  });
});
