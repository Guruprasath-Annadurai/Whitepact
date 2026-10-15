// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
export const onboardingDraftKey = "whitepact-onboarding-draft";
export type OnboardingData = { organization_name: string; website: string; role: string; intended_use: string; use_case: string; plan: "FREE" | "PRO" | "ENTERPRISE" };
export const defaultOnboardingData: OnboardingData = { organization_name: "", website: "", role: "", intended_use: "", use_case: "Agent development", plan: "FREE" };

export function readOnboardingDraft(): { step: number; data: OnboardingData } {
  const fallback = { step: 1, data: { ...defaultOnboardingData } };
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(onboardingDraftKey) ?? "null");
    if (!value || typeof value !== "object" || Array.isArray(value)) return fallback;
    const saved = value as Record<string, unknown>;
    if (!saved.data || typeof saved.data !== "object" || Array.isArray(saved.data)) return fallback;
    const input = saved.data as Record<string, unknown>;
    const data = { ...defaultOnboardingData };
    for (const field of ["organization_name", "website", "role", "intended_use", "use_case"] as const) {
      if (typeof input[field] === "string" && input[field].length <= 4096) data[field] = input[field];
    }
    if (["FREE", "PRO", "ENTERPRISE"].includes(String(input.plan))) data.plan = input.plan as OnboardingData["plan"];
    const step = typeof saved.step === "number" && Number.isInteger(saved.step) && saved.step >= 1 && saved.step <= 3 ? saved.step : 1;
    return { step, data };
  } catch { return fallback; }
}

export function storeOnboardingDraft(step: number, data: OnboardingData): boolean {
  try { sessionStorage.setItem(onboardingDraftKey, JSON.stringify({ step, data })); return true; }
  catch { return false; }
}

export function clearOnboardingDraft(): void {
  try { sessionStorage.removeItem(onboardingDraftKey); } catch { /* Storage can be unavailable; server success remains authoritative. */ }
}
