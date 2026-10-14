// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { EvidenceContractPanel } from "../features/dashboard/CanonicalPanels";
import { boundedEvidenceExport } from "../lib/evidenceExport";

afterEach(() => vi.restoreAllMocks());
const record = { evidence_id: "safe-id", action_type: "supported.tool", target: "safe-target", decision: "DENY", hash: "returned-hash" };
const verification = { status: "VALID", chain_intact: true, integrity_note: "Returned backend verification", cryptographically_signed: false };
function mount() { render(<MemoryRouter><EvidenceContractPanel records={[record]} /></MemoryRouter>); }

it("exports only returned scalar evidence fields, not credentials, raw arguments or invented signatures", () => {
  const result = boundedEvidenceExport([{ ...record, api_key: "fake-canary", args: { password: "fake-canary" }, root_proof: "fake-canary", outcome_status: "UNKNOWN" }]);
  expect(JSON.stringify(result)).not.toContain("fake-canary");
  expect(result.records[0].outcome_status).toBe("UNKNOWN");
  expect(result.records[0].hash).toBe("returned-hash");
  expect(result.scope).toMatch(/not complete history.*signed attestation/);
});

it.each(["ALLOW_WITH_REDACTION", "QUARANTINE"])("queries the canonical %s decision without coercing it", async (decision) => {
  const fetch = vi.spyOn(window, "fetch").mockImplementation(async (url) => Response.json(String(url).endsWith("verify") ? verification : { evidence: [{ ...record, decision }] }));
  mount();
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Decision" }), decision);
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => String(url).includes(`decision=${decision}`))).toBe(true));
  expect(await screen.findByText(decision)).toBeInTheDocument();
});

it("does not let an older filter response replace the currently selected decision", async () => {
  let finishOld: ((value: Response) => void) | undefined;
  vi.spyOn(window, "fetch").mockImplementation(async (url) => {
    if (String(url).endsWith("verify")) return Response.json(verification);
    if (String(url).includes("decision=DENY")) return new Promise<Response>((resolve) => { finishOld = resolve; });
    return Response.json({ evidence: [{ ...record, decision: "QUARANTINE" }] });
  }); mount();
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Decision" }), "DENY");
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Decision" }), "QUARANTINE");
  await screen.findByText("QUARANTINE");
  finishOld?.(Response.json({ evidence: [{ ...record, decision: "DENY" }] }));
  await waitFor(() => expect(screen.queryByText("DENY")).not.toBeInTheDocument());
});

it.each([null, {}, { status: "VALID" }])("does not claim a valid chain from malformed verification", async (payload) => {
  vi.spyOn(window, "fetch").mockResolvedValue(Response.json(payload)); mount();
  expect(await screen.findByRole("alert")).toHaveTextContent("Evidence verification unavailable");
  expect(screen.queryByText("VALID")).not.toBeInTheDocument();
});

it("does not combine another evidence record with the requested attestation", async () => {
  vi.spyOn(window, "fetch").mockImplementation(async (url) => Response.json(String(url).endsWith("verify") ? verification : String(url).endsWith("attestation") ? { evidence_id: "safe-id", decision: "DENY", cryptographically_signed: false } : { ...record, evidence_id: "other-id" }));
  mount(); await userEvent.click(screen.getByRole("button", { name: "View evidence" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Evidence detail could not be confirmed");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
