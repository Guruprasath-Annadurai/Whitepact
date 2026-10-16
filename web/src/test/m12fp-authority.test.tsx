// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CustomerAuthorityPreparation, type AuthorityPreparationState } from "../features/authority/CustomerAuthorityPreparation";

describe("inactive customer authority preparation", () => {
  it("cannot initiate authority operations", () => {
    render(<CustomerAuthorityPreparation />);
    for (const button of screen.getAllByRole("button")) expect(button).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("No security operation can be submitted");
    expect(screen.getByText(/No consent has been recorded/)).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
  it.each<AuthorityPreparationState["kind"]>(["loading", "authentication-required", "forbidden", "expired", "unknown", "error"])("preserves %s without enabling mutation", (kind) => {
    render(<CustomerAuthorityPreparation state={{ kind }} />);
    const role = ["unknown", "error", "forbidden", "expired"].includes(kind) ? "alert" : "status";
    expect(screen.getByRole(role)).toBeInTheDocument();
    for (const button of screen.getAllByRole("button")) expect(button).toBeDisabled();
    expect(screen.getByText(/No vote count or recovery approval is calculated here/)).toBeInTheDocument();
  });
  it("keeps uncertain operations separate from confirmed containment", () => {
    render(<CustomerAuthorityPreparation state={{ kind: "unknown" }} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Do not repeat the operation");
    expect(screen.getByText(/Pending or UNKNOWN is not contained/)).toBeInTheDocument();
  });
});
