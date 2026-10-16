// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { OnboardingPage } from "../features/onboarding/OnboardingPage";
import { onboardingDraftKey } from "../lib/onboardingDraft";

afterEach(() => { sessionStorage.clear(); vi.restoreAllMocks(); });

it("names each choice group and moves focus on forward and back navigation", async () => {
  const user = userEvent.setup();
  const fetch = vi.spyOn(window, "fetch");
  render(<MemoryRouter><OnboardingPage /></MemoryRouter>);
  expect(screen.getByRole("heading", { level: 1 })).toHaveFocus();
  expect(screen.getByText("Organization").closest("li")).toHaveAttribute("aria-current", "step");
  await user.type(screen.getByLabelText("Organization name"), "Accessible workspace");
  await user.selectOptions(screen.getByLabelText("Your role"), "Engineering");
  await user.click(screen.getByRole("button", { name: /Continue/ }));
  expect(screen.getByRole("heading", { name: "Choose your use case" })).toHaveFocus();
  expect(screen.getByText("Use case").closest("li")).toHaveAttribute("aria-current", "step");
  expect(screen.getByText("Organization").closest("li")).not.toHaveAttribute("aria-current");
  const useCase = screen.getByRole("group", { name: "Use case" });
  await user.click(within(useCase).getByLabelText("MCP security"));
  await user.click(screen.getByRole("button", { name: /Continue/ }));
  expect(screen.getByRole("heading", { name: "Choose a plan preference" })).toHaveFocus();
  expect(within(screen.getByRole("group", { name: "Plan preference" })).getByLabelText(/Community/)).toBeChecked();
  await user.click(screen.getByRole("button", { name: "Back" }));
  expect(screen.getByRole("heading", { name: "Choose your use case" })).toHaveFocus();
  expect(screen.getByLabelText("MCP security")).toBeChecked();
  expect(fetch).not.toHaveBeenCalled();
});

it("focuses the restored draft step without submitting or changing its plan preference", () => {
  sessionStorage.setItem(onboardingDraftKey, JSON.stringify({ step: 3, data: { organization_name: "Draft", plan: "PRO" } }));
  const fetch = vi.spyOn(window, "fetch");
  render(<MemoryRouter><OnboardingPage /></MemoryRouter>);
  expect(screen.getByRole("heading", { name: "Choose a plan preference" })).toHaveFocus();
  expect(screen.getByText("Plan", { selector: "strong" }).closest("li")).toHaveAttribute("aria-current", "step");
  expect(screen.getByRole("radio", { name: /Pro preference/ })).toBeChecked();
  expect(fetch).not.toHaveBeenCalled();
});
