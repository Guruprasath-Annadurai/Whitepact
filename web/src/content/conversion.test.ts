// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { describe, expect, it } from "vitest";
import corporate from "./corporate.json";
import { controlChain } from "./control-chain";

describe("evaluation paths preserve technical truth", () => {
  it("separates authentication from supported action authority for builders", () => {
    const copy = corporate.developers.sections.find(([heading]) => heading === "For agent and MCP builders")?.[1];
    expect(copy).toContain("Authentication establishes who an agent is");
    expect(copy).toContain("supported boundary");
    expect(copy).toContain("UNKNOWN");
  });
  it("makes ungoverned paths and non-authoritative discovery explicit", () => {
    const copy = corporate.developers.sections.find(([heading]) => heading === "For AI infrastructure teams")?.[1];
    expect(copy).toContain("outside its boundary");
    expect(copy).toContain("not automatically authorized");
  });
  it("does not convert demonstrations into traction or certification", () => {
    const copy = corporate.enterprise.sections.find(([heading]) => heading === "A focused evaluation for founders and investors")?.[1];
    expect(copy).toContain("not customer traction, production adoption or certification");
  });
  it("retains the exact conceptual chain instead of inventing runtime telemetry", () => {
    expect(controlChain).toEqual(["Constitution", "Identity", "Authority", "Intent", "Policy", "Capability Graph", "Risk", "Approval", "Judgment", "Short-Lived Execution Grant", "Isolated Execution", "Evidence", "Audit", "Revocation"]);
  });
});
