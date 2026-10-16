// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { act, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { DomainPage } from "../features/dashboard/DomainPage";

afterEach(() => vi.restoreAllMocks());
function workspace(id: string) {
  const session = { user: { email: "owner@example.com", full_name: "Owner" }, organization: { id, name: id, plan: "FREE" } };
  return <MemoryRouter><Routes><Route element={<Outlet context={session} />}><Route index element={<DomainPage domainKey="security" />} /></Route></Routes></MemoryRouter>;
}
const response = (status: string) => new Response(JSON.stringify({ source: "identity", items: [{ title: "Assurance", status }] }));

it("cancels the previous workspace read and ignores a late response even if transport ignores cancellation", async () => {
  let finish!: (value: Response) => void;
  const fetcher = vi.spyOn(window, "fetch").mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; })).mockResolvedValueOnce(response("CURRENT"));
  const view = render(workspace("first"));
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
  const signal = fetcher.mock.calls[0][1]?.signal;
  view.rerender(workspace("second"));
  expect(signal?.aborted).toBe(true);
  expect(await screen.findByText("CURRENT")).toBeInTheDocument();
  await act(async () => finish(response("STALE")));
  expect(screen.queryByText("STALE")).not.toBeInTheDocument();
  expect(screen.getByText("CURRENT")).toBeInTheDocument();
});

it.each([null, { items: null, source: "identity" }, { items: [null], source: "identity" }, { items: [], source: false }])("rejects malformed domain records without presenting an empty dataset: %j", async (payload) => {
  vi.spyOn(window, "fetch").mockResolvedValue(new Response(JSON.stringify(payload)));
  render(workspace("first"));
  expect(await screen.findByRole("alert")).toHaveTextContent("could not be confirmed");
  expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  expect(screen.queryByText("Unavailable")).not.toBeInTheDocument();
});
