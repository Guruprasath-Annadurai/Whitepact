// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SignupPage } from "../features/auth/AuthPages";
import { ApiKeysPage } from "../features/api-keys/ApiKeysPage";

describe("account and credential flows", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("links signup consent to the legal documents and enforces password quality", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><SignupPage /></MemoryRouter>);
    expect(screen.getByRole("link", { name: "Terms of Service" })).toHaveAttribute("href", "/terms");
    expect(screen.getByRole("link", { name: "Privacy Policy" })).toHaveAttribute("href", "/privacy");
    const submit = screen.getByRole("button", { name: /Create account/i });
    expect(submit).toBeDisabled();
    await user.type(screen.getByLabelText("Password"), "StrongPassword1!");
    expect(submit).toBeEnabled();
  });

  it("creates a key, discloses the secret once, and closes with Escape", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(window, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ keys: [] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        id: "key-1", name: "CI Agent", prefix: "wp_test_abcd", environment: "test",
        scopes: ["governance:read"], created_at: "2026-09-06T00:00:00Z",
        last_used_at: null, expires_at: null, status: "active", api_key: "wp_test_secret-once",
      }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ keys: [] }), { status: 200 }));

    render(<MemoryRouter initialEntries={["/dashboard/api-keys"]}><Routes><Route path="/dashboard/api-keys" element={<ApiKeysPage />} /></Routes></MemoryRouter>);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    await user.click(screen.getAllByRole("button", { name: /Create API Key/i })[0]);
    expect(screen.getByRole("dialog", { name: "Create API key" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Name"), "CI Agent");
    await user.click(screen.getByRole("button", { name: "Create key" }));
    expect(await screen.findByText("wp_test_secret-once")).toBeInTheDocument();
    expect(screen.getByText(/only time the full secret is displayed/i)).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("rotates and revokes an existing key through confirmed mutations", async () => {
    const user = userEvent.setup();
    const existing = {
      id: "key-old", name: "Runtime", prefix: "wp_test_old", environment: "test",
      scopes: ["governance:read"], created_at: "2026-09-01T00:00:00Z",
      last_used_at: null, expires_at: null, status: "active",
    };
    const replacement = { ...existing, id: "key-new", prefix: "wp_test_new", api_key: "wp_test_rotated-secret" };
    const fetchMock = vi.spyOn(window, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ keys: [existing] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(replacement), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ keys: [replacement] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ revoked: "key-new" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ keys: [] }), { status: 200 }));
    render(<MemoryRouter><ApiKeysPage /></MemoryRouter>);
    expect(await screen.findByText("wp_test_old")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Rotate/i }));
    await user.click(screen.getByRole("button", { name: "Confirm rotate" }));
    expect(await screen.findByText("wp_test_rotated-secret")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Done" }));
    expect(await screen.findByText("wp_test_new")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Revoke/i }));
    await user.click(screen.getByRole("button", { name: "Confirm revoke" }));
    expect(await screen.findByText("No API keys")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(5);
  });
});
