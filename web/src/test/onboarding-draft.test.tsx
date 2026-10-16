// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OnboardingPage } from "../features/onboarding/OnboardingPage";
import { onboardingDraftKey, readOnboardingDraft } from "../lib/onboardingDraft";

afterEach(() => { vi.restoreAllMocks(); sessionStorage.clear(); });
describe("untrusted session-only onboarding draft", () => {
  it.each(["broken JSON", "[]", "null", '{"step":999,"data":"wrong"}'])("ignores malformed draft %s", (raw) => {
    sessionStorage.setItem(onboardingDraftKey, raw);
    expect(readOnboardingDraft().step).toBe(1);
    render(<MemoryRouter><OnboardingPage /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Tell us about your organization" })).toBeInTheDocument();
  });
  it("whitelists fields and refuses persisted authority/entitlement injection", () => {
    sessionStorage.setItem(onboardingDraftKey, JSON.stringify({step:-1,data:{organization_name:"Local org",plan:"ADMIN",organization_id:"forged",root_authority:true}}));
    const draft=readOnboardingDraft();
    expect(draft.step).toBe(1); expect(draft.data.plan).toBe("FREE");
    expect(draft.data).not.toHaveProperty("organization_id"); expect(draft.data).not.toHaveProperty("root_authority");
  });
  it("remains usable and reports when storage is unavailable", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new DOMException("Storage unavailable"); });
    render(<MemoryRouter><OnboardingPage /></MemoryRouter>);
    expect(screen.getByText(/Draft values will not survive a refresh/i)).toBeInTheDocument();
    expect(screen.getByRole("button", {name:/Continue/})).toBeEnabled();
  });
});
