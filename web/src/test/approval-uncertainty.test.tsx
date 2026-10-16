// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApprovalContractPanel } from "../features/dashboard/CanonicalPanels";
import { approvalResourceSegment, executionAcknowledgement } from "../lib/approvalOutcome";

const detail = { approval_id: "approval-local", action_type: "supported.action", target: "reviewed-target", status: "PENDING", required_approvals: 1, current_vote_count: 0, votes: [] };
afterEach(() => vi.restoreAllMocks());

describe("consequential approval uncertainty", () => {
  it("encodes opaque references and refuses path-only dot segments", () => {
    expect(approvalResourceSegment("../other?query=1")).toBe("..%2Fother%3Fquery%3D1");
    for (const invalid of ["", ".", ".."]) expect(() => approvalResourceSegment(invalid)).toThrow("Invalid approval reference");
  });
  it("does not accept another approval's acknowledgement", () => {
    expect(executionAcknowledgement("expected", {approval_id:"other",execution_status:"SUCCEEDED",message:"ok",reconciliation_required:false}).state).toBe("UNKNOWN");
  });
  it.each(["lost response", "server failure", "malformed success", "contradictory success"])("does not assert failure or allow repeat after %s", async (failure) => {
    let executions = 0;
    const fetchMock = vi.spyOn(window, "fetch").mockImplementation(async (path, init) => {
      if (String(path).endsWith("/resolve")) return Response.json({ status: "APPROVED" });
      if (String(path).endsWith("/execute")) {
        executions++;
        expect(init?.method).toBe("POST");
        if (failure === "lost response") throw new TypeError("Network request failed");
        if (failure === "server failure") return Response.json({ detail: "Unavailable" }, { status: 503 });
        if (failure === "malformed success") return Response.json(null);
        return Response.json({ approval_id: detail.approval_id, execution_status: "SUCCEEDED", reconciliation_required: true, message: "Conflicting state", evidence_id: null, outcome_id: null });
      }
      return Response.json(detail);
    });
    render(<MemoryRouter><ApprovalContractPanel records={[detail]} onError={vi.fn()} onChanged={vi.fn(async () => undefined)} /></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm approved" }));
    expect(await screen.findByRole("heading", { name: "Execution outcome is uncertain" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Deny" })).toBeDisabled();
    expect(screen.getByText(/Do not retry/i)).toBeInTheDocument();
    await waitFor(() => expect(executions).toBe(1));
    expect(fetchMock.mock.calls.filter(([path]) => String(path).endsWith("/execute"))).toHaveLength(1);
  });

  it("keeps a lost vote distinct from an uncertain execution", async () => {
    let executions = 0;
    vi.spyOn(window, "fetch").mockImplementation(async (path) => {
      if (String(path).endsWith("/resolve")) throw new TypeError("Lost vote acknowledgement");
      if (String(path).endsWith("/execute")) executions++;
      return Response.json(detail);
    });
    render(<MemoryRouter><ApprovalContractPanel records={[detail]} onError={vi.fn()} onChanged={vi.fn(async () => undefined)} /></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm approved" }));
    expect(await screen.findByRole("heading", { name: "Approval outcome is uncertain" })).toBeInTheDocument();
    expect(screen.getByText(/No execution request was sent/i)).toBeInTheDocument();
    expect(executions).toBe(0);
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
  });
});
