// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AgentInventoryPreparation, type AgentInventoryReadState } from "../features/inventory/AgentInventoryPreparation";

const agents = [{ id: "agent-long-".repeat(40), displayName: "Declared customer agent", lifecycleState: "UNKNOWN_FUTURE_STATE", reportedActiveDelegation: true }];

describe("production-unwired read-only inventory preparation", () => {
  it("does not present returned records when read capability is absent", () => {
    render(<AgentInventoryPreparation state={{ status: "ready", agents }} />);
    expect(screen.getByRole("status")).toHaveTextContent("Agent inventory unavailable");
    expect(screen.queryByText("Declared customer agent")).not.toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Returned agent registrations" })).not.toBeInTheDocument();
  });

  it.each<[AgentInventoryReadState, string, string]>([
    [{ status: "loading" }, "status", "Loading backend-reported agent inventory"],
    [{ status: "unavailable" }, "status", "Agent inventory unavailable"],
    [{ status: "error" }, "alert", "No empty or successful result is claimed"],
    [{ status: "ready", agents: [] }, "status", "No agent registrations were returned by this read"],
  ])("distinguishes the %s read state", (state, role, text) => {
    render(<AgentInventoryPreparation state={state} readContractAvailable />);
    expect(screen.getByRole(role)).toHaveTextContent(text);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("preserves unknown lifecycle and reported delegation without inferring permission or a graph", () => {
    render(<AgentInventoryPreparation state={{ status: "ready", agents }} readContractAvailable />);
    expect(screen.getByRole("heading", { level: 2, name: "Agent inventory" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Returned agent registrations" })).toBeInTheDocument();
    expect(screen.getByText("UNKNOWN_FUTURE_STATE")).toBeInTheDocument();
    expect(screen.getByText("Reported active — not execution authority")).toBeInTheDocument();
    expect(screen.getByText(/Neither registration nor a reported delegation authorizes an action/)).toBeInTheDocument();
    expect(screen.getByText(/A delegation flag cannot reconstruct a graph or effective authority/)).toBeInTheDocument();
    expect(screen.getByText(agents[0].id)).toHaveStyle({ overflowWrap: "anywhere" });
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("does not turn missing active delegation into denied or revoked authority", () => {
    render(<AgentInventoryPreparation state={{ status: "ready", agents: [{ ...agents[0], lifecycleState: "", reportedActiveDelegation: false }] }} readContractAvailable />);
    expect(screen.getByText("Not provided")).toBeInTheDocument();
    expect(screen.getByText("No active delegation reported — no authority conclusion")).toBeInTheDocument();
    for (const label of ["Application inventory", "Policy bindings", "Credential inventory", "Delegation graph"]) expect(screen.getByText(new RegExp(`${label}: no integrated customer contract`))).toBeInTheDocument();
    expect(screen.getByText(/Integration preparation — not available in the customer console/)).toBeInTheDocument();
  });
});
