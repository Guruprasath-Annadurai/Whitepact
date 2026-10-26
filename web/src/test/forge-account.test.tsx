// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { AccountPage } from "../features/dashboard/AccountPage";

it("shows literal session details and keyboard navigation without claiming authority or sending a mutation", async () => {
  const fetcher = vi.spyOn(window, "fetch");
  const user = userEvent.setup();
  const session = { user: { full_name: "<Account owner>", email: "owner@example.com" }, organization: { name: "Workspace", id: "org-1", plan: "FREE" } };
  render(<MemoryRouter><Routes><Route element={<Outlet context={session} />}><Route index element={<AccountPage />} /></Route><Route path="/forgot-password" element={<h1>Password reset route</h1>} /></Routes></MemoryRouter>);
  expect(screen.getByText("<Account owner>")).toBeInTheDocument();
  expect(screen.getByText("owner@example.com")).toBeInTheDocument();
  expect(screen.getByText(/does not confirm identity assurance/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Read backend security posture" })).toHaveAttribute("href", "/dashboard/security");
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
  await user.tab();
  expect(screen.getByRole("link", { name: "Request a password reset" })).toHaveFocus();
  await user.keyboard("{Enter}");
  expect(screen.getByRole("heading", { name: "Password reset route" })).toBeInTheDocument();
  expect(fetcher).not.toHaveBeenCalled();
  fetcher.mockRestore();
});
