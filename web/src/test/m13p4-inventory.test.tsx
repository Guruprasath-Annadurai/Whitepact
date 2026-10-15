// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AgentInventoryPreparation } from "../features/inventory/AgentInventoryPreparation";

const agents = Array.from({ length: 12 }, (_, index) => ({ id: `agent-${index}`, displayName: `Agent ${index}`, lifecycleState: index === 11 ? "FUTURE_STATE" : "REGISTERED", reportedActiveDelegation: false }));

describe("M13-P4 inventory preparation", () => {
  it("paginates only loaded registrations with accessible controls and truthful scope", () => {
    render(<AgentInventoryPreparation state={{ status: "ready", agents }} readContractAvailable />);
    expect(screen.getByText("Showing 1–10 of 12 matching loaded registrations.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Agent 11" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous loaded page" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Next loaded page" }));
    expect(screen.getByRole("heading", { name: "Agent 11" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next loaded page" })).toBeDisabled();
    expect(screen.getByText(/backend read has no pagination or total-count contract/)).toBeInTheDocument();
  });

  it("filters all loaded pages by ID, name and unknown status without changing authority", () => {
    render(<AgentInventoryPreparation state={{ status: "ready", agents }} readContractAvailable />);
    const filter = screen.getByRole("searchbox", { name: "Filter loaded agent registrations" });
    fireEvent.change(filter, { target: { value: "future_state" } });
    expect(screen.getByRole("heading", { name: "Agent 11" })).toBeInTheDocument();
    expect(screen.getByText("FUTURE_STATE")).toBeInTheDocument();
    expect(screen.getByText(/registration and delegation status do not describe executable capabilities/)).toBeInTheDocument();
    fireEvent.change(filter, { target: { value: "missing" } });
    expect(screen.getByText("No loaded agent registrations match this filter.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Agent 11" })).not.toBeInTheDocument();
    fireEvent.change(filter, { target: { value: "agent-2" } });
    expect(screen.getByRole("heading", { name: "Agent 2" })).toBeInTheDocument();
    fireEvent.change(filter, { target: { value: " Agent 7 " } });
    expect(screen.getByRole("heading", { name: "Agent 7" })).toBeInTheDocument();
  });

  it("removes records and controls immediately when the read becomes unavailable or fails", () => {
    const { rerender } = render(<AgentInventoryPreparation state={{ status: "ready", agents }} readContractAvailable />);
    rerender(<AgentInventoryPreparation state={{ status: "error" }} readContractAvailable />);
    expect(screen.getByRole("alert")).toHaveTextContent("could not be confirmed");
    expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Agent 0" })).not.toBeInTheDocument();
    rerender(<AgentInventoryPreparation state={{ status: "ready", agents }} />);
    expect(screen.getByRole("status")).toHaveTextContent("Agent inventory unavailable");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
