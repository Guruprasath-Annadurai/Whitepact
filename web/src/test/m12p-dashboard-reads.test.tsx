// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { act, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApprovalContractPanel } from "../features/dashboard/CanonicalPanels";

const pending = { approval_id: "approval-one", action_type: "supported.action", target: "reviewed target", status: "PENDING", required_approvals: 2, current_vote_count: 0, votes: [] };
function deferred() {
  let resolve!: (response: Response) => void;
  const promise = new Promise<Response>((done) => { resolve = done; });
  return { promise, resolve };
}
function panel(records: typeof pending[]) {
  return <MemoryRouter><ApprovalContractPanel records={records} onError={vi.fn()} onChanged={vi.fn(async () => undefined)} /></MemoryRouter>;
}
afterEach(() => vi.restoreAllMocks());

describe("canonical approval read lifecycle", () => {
  it("makes one canonical read per unique approval reference in a refresh", async () => {
    const fetch = vi.spyOn(window, "fetch").mockResolvedValue(Response.json(pending));
    render(panel([pending, { ...pending }]));
    await screen.findAllByRole("button", { name: "Approve" });
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("does not let an obsolete PENDING response overwrite refreshed DENIED state even if transport ignores abort", async () => {
    const old = deferred(); const fresh = deferred();
    const fetch = vi.spyOn(window, "fetch").mockImplementationOnce(() => old.promise).mockImplementationOnce(() => fresh.promise);
    const view = render(panel([pending]));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    const oldSignal = fetch.mock.calls[0][1]?.signal;
    view.rerender(panel([{ ...pending, status: "DENIED" }]));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    await act(async () => { fresh.resolve(Response.json({ ...pending, status: "DENIED" })); });
    expect(await screen.findByRole("button", { name: "Approve" })).toBeDisabled();
    await act(async () => { old.resolve(Response.json(pending)); });
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
    expect(oldSignal?.aborted).toBe(true);
  });

  it("hides the previous refresh detail and its action controls while a new canonical read is pending", async () => {
    const next = deferred();
    const fetch = vi.spyOn(window, "fetch").mockResolvedValueOnce(Response.json(pending)).mockImplementationOnce(() => next.promise);
    const view = render(panel([pending]));
    await screen.findByRole("button", { name: "Approve" });
    view.rerender(panel([{ ...pending }]));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Loading canonical approval detail");
    await act(async () => { next.resolve(Response.json({ ...pending, status: "CONSUMED" })); });
    expect(await screen.findByRole("button", { name: "Approve" })).toBeDisabled();
  });

  it("aborts a canonical read when the panel unmounts", async () => {
    const request = deferred();
    const fetch = vi.spyOn(window, "fetch").mockImplementation(() => request.promise);
    const view = render(panel([pending]));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    const signal = fetch.mock.calls[0][1]?.signal;
    view.unmount();
    expect(signal?.aborted).toBe(true);
    await act(async () => { request.resolve(Response.json(pending)); });
  });

  it("does not expose mutation controls for a mismatched detail acknowledgement", async () => {
    vi.spyOn(window, "fetch").mockResolvedValue(Response.json({ ...pending, approval_id: "another-approval" }));
    render(panel([pending]));
    expect(await screen.findByRole("alert")).toHaveTextContent("Approval detail could not be confirmed");
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  it("does not leave an old confirmation actionable after the approval list refreshes", async () => {
    const next = deferred();
    const fetch = vi.spyOn(window, "fetch").mockResolvedValueOnce(Response.json(pending)).mockImplementationOnce(() => next.promise);
    const view = render(panel([pending]));
    await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
    expect(screen.getByRole("button", { name: "Confirm approved" })).toBeInTheDocument();
    view.rerender(panel([{ ...pending, status: "DENIED" }]));
    expect(screen.queryByRole("button", { name: "Confirm approved" })).not.toBeInTheDocument();
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    expect(fetch.mock.calls.every(([, init]) => !init?.method || init.method === "GET")).toBe(true);
    await act(async () => { next.resolve(Response.json({ ...pending, status: "DENIED" })); });
  });

  it("shows loading during an explicit failed-read retry and recovers with the backend state", async () => {
    const retry = deferred();
    const fetch = vi.spyOn(window, "fetch").mockRejectedValueOnce(new TypeError("Network unavailable")).mockImplementationOnce(() => retry.promise);
    render(panel([pending]));
    await userEvent.click(await screen.findByRole("button", { name: "Retry detail" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Loading canonical approval detail");
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    await act(async () => { retry.resolve(Response.json({ ...pending, status: "DENIED" })); });
    expect(await screen.findByRole("button", { name: "Approve" })).toBeDisabled();
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("does not leave an invalid empty reference in perpetual loading or make a request", async () => {
    const fetch = vi.spyOn(window, "fetch");
    render(panel([{ ...pending, approval_id: "" }]));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid approval reference");
    expect(fetch).not.toHaveBeenCalled();
  });
});
