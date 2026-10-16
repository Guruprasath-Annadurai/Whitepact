// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { ApiKeysPage } from "../features/api-keys/ApiKeysPage";
import { readKeyInventory } from "../lib/apiKeyInventory";

const key = { id: "key-1", name: "Local", prefix: "wp_test_1", environment: "test", scopes: ["governance:read"], created_at: "2026-10-16T00:00:00Z", last_used_at: null, expires_at: null, status: "unknown" };
afterEach(() => vi.restoreAllMocks());
it("projects list metadata without retaining a raw secret or normalizing unknown status", () => {
  expect(readKeyInventory({ keys: [{ ...key, api_key: "SECRET" }] })).toEqual([key]);
});
it.each([{ keys: null }, { keys: [key, key] }, { keys: [{ ...key, scopes: "write" }] }, { keys: [{ ...key, created_at: "invalid" }] }, { keys: [{ ...key, last_used_at: false }] }])("rejects malformed inventory %j", (value) => {
  expect(() => readKeyInventory(value)).toThrow("could not be confirmed");
});
it("renders a retryable read failure instead of crashing or claiming no keys", async () => {
  vi.spyOn(window, "fetch").mockResolvedValue(new Response(JSON.stringify({ keys: [{ ...key, scopes: null }] })));
  render(<MemoryRouter><ApiKeysPage /></MemoryRouter>);
  expect(await screen.findByRole("alert")).toHaveTextContent("metadata could not be confirmed");
  expect(screen.queryByText("No API keys")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
});
