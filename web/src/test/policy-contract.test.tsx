// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { PolicyPage } from "../features/policy/PolicyPage";

afterEach(() => vi.restoreAllMocks());

it("offers only effects accepted by the canonical ordered PolicyRule constructor", async () => {
  vi.spyOn(window, "fetch").mockResolvedValue(new Response(JSON.stringify({
    org_id: "fixture-org", rules: [], can_edit: true,
  }), { status: 200 }));
  const Parent = () => <Outlet context={{ organization: { role: "OWNER" } }} />;
  render(<MemoryRouter><Routes><Route element={<Parent />}><Route path="/" element={<PolicyPage />} /></Route></Routes></MemoryRouter>);
  const effect = await screen.findByRole("combobox", { name: "Effect" });
  expect(Array.from(effect.querySelectorAll("option"), (option) => option.value))
    .toEqual(["ALLOW", "DENY", "REQUIRE_APPROVAL"]);
  expect(screen.getByText(/not editable rule effects/)).toBeInTheDocument();
});
