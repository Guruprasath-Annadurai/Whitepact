// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { PolicyHistory } from "../features/policy/PolicyHistory";
afterEach(() => vi.restoreAllMocks());

it("reads the supported endpoint without sending tenant identity and distinguishes server verification from a checkpoint", async () => {
  const fetch = vi.spyOn(window, "fetch").mockResolvedValue(Response.json({ chain_valid: true, checkpoint_checked: false, head: { version: 2, entry_digest: "returned-digest" }, entries: [] }));
  render(<PolicyHistory />);
  await userEvent.click(screen.getByRole("button", { name: "Load policy history" }));
  expect(await screen.findByText(/Backend reports chain valid/)).toHaveTextContent("No external checkpoint was checked");
  expect(fetch.mock.calls[0][0]).toBe("/api/v1/web/policy/history?limit=100");
  expect(fetch.mock.calls[0][1]?.body).toBeUndefined();
});

it.each([null, {}, { chain_valid: true, checkpoint_checked: false, head: null, entries: [{}] }])("does not promote malformed history into valid evidence", async (payload) => {
  vi.spyOn(window, "fetch").mockResolvedValue(Response.json(payload)); render(<PolicyHistory />);
  await userEvent.click(screen.getByRole("button", { name: "Load policy history" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("No valid history is claimed");
  expect(screen.queryByText(/Backend reports chain valid/)).not.toBeInTheDocument();
});
