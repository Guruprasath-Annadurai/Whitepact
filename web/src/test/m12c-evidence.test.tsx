// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { EvidenceContractPanel } from "../features/dashboard/CanonicalPanels";

afterEach(() => vi.restoreAllMocks());
const record = { evidence_id: "evidence-1", decision: "DENY", hash: "returned-hash" };
const attestation = { ...record, evidence_hash: record.hash, outcome_status: "UNKNOWN", reconciliation_status: "UNRESOLVED", cryptographically_signed: false };
function mount(attested = attestation, chainIntact = false) {
  vi.spyOn(window, "fetch").mockImplementation(async (url) => Response.json(
    String(url).endsWith("verify") ? { status: chainIntact ? "VALID" : "INVALID", chain_intact: chainIntact, cryptographically_signed: false, integrity_note: "Backend verification result" }
      : String(url).endsWith("attestation") ? attested : record,
  ));
  render(<MemoryRouter><EvidenceContractPanel records={[record]} /></MemoryRouter>);
}

it("never presents an unsigned attestation as established integrity or confirmed external success", async () => {
  mount();
  await userEvent.click(screen.getByRole("button", { name: "View evidence" }));
  await screen.findByRole("dialog");
  expect(screen.queryByText(/Integrity is established/)).not.toBeInTheDocument();
  expect(screen.getByText(/not independent proof of integrity or downstream execution/)).toBeInTheDocument();
  expect(screen.getByText("UNKNOWN")).toBeInTheDocument();
  expect(screen.getByText("Reconciliation required")).toBeInTheDocument();
});

it("rejects a contradictory attestation decision even when its ID and hash match", async () => {
  mount({ ...attestation, decision: "ALLOW" });
  await userEvent.click(screen.getByRole("button", { name: "View evidence" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Evidence detail could not be confirmed");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("shows a pending detail read rather than leaving the user without request status", async () => {
  vi.spyOn(window, "fetch").mockImplementation(() => new Promise<Response>(() => {}));
  render(<MemoryRouter><EvidenceContractPanel records={[record]} /></MemoryRouter>);
  await userEvent.click(screen.getByRole("button", { name: "View evidence" }));
  expect(screen.getByRole("status")).toHaveTextContent("Loading evidence detail");
});

it.each([
  { status: "INVALID", chain_intact: true },
  { status: "INCOMPLETE", chain_intact: false },
])("rejects contradictory verification fields: $status", async (payload) => {
  vi.spyOn(window, "fetch").mockResolvedValue(Response.json({ ...payload, cryptographically_signed: false, integrity_note: "Contradictory response" }));
  render(<MemoryRouter><EvidenceContractPanel records={[record]} /></MemoryRouter>);
  expect(await screen.findByRole("alert")).toHaveTextContent("No valid chain is claimed");
  expect(screen.queryByText(payload.status)).not.toBeInTheDocument();
});
