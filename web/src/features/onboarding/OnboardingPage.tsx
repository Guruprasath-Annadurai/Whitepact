// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { FormEvent, useEffect, useRef, useState } from "react";
import { Building2, Check, KeyRound, ShieldCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Brand } from "../../components/Brand";
import { Button } from "../../components/Button";
import { api } from "../../lib/api";
import { clearOnboardingDraft, readOnboardingDraft, storeOnboardingDraft } from "../../lib/onboardingDraft";

const steps = [
  ["Organization", "Workspace details"],
  ["Use case", "How you will use WhitePact"],
  ["Plan", "Record a plan preference"],
] as const;

export function OnboardingPage() {
  const navigate = useNavigate();
  const [saved] = useState(readOnboardingDraft);
  const [step, setStep] = useState(saved.step);
  const [data, setData] = useState(saved.data);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [draftAvailable, setDraftAvailable] = useState(true);
  const submitting = useRef(false);
  useEffect(() => { setDraftAvailable(storeOnboardingDraft(step, data)); }, [step, data]);

  async function next(event: FormEvent) {
    event.preventDefault();
    if (submitting.current) return;
    setError("");
    if (step < steps.length) { setStep(step + 1); return; }
    submitting.current = true; setBusy(true);
    try {
      const result = await api<{ next: string }>("/api/v1/web/onboarding", { method: "POST", body: JSON.stringify(data) });
      if (!result || result.next !== "/dashboard") throw new Error("Workspace creation was not confirmed. Check your session before submitting again.");
      clearOnboardingDraft();
      navigate(result.next);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not complete onboarding"); }
    finally { submitting.current = false; setBusy(false); }
  }

  return <main className="onboarding"><header><Brand /><a href="/docs">Docs ↗</a></header><div className="onboarding-grid"><ol className="step-rail">{steps.map(([name, copy], index) => { const number = index + 1; return <li key={name} className={number < step ? "done" : number === step ? "active" : ""}><span>{number < step ? <Check /> : number}</span><div><strong>{name}</strong><small>{copy}</small></div></li>; })}</ol><section className="onboarding-form"><span>Step {step} of {steps.length}</span><h1>{step === 1 ? "Tell us about your organization" : step === 2 ? "Choose your use case" : "Choose a plan preference"}</h1><form onSubmit={next} aria-describedby={error ? "onboarding-error" : undefined}>{step === 1 && <><label className="field"><span>Organization name</span><input value={data.organization_name} onChange={(e) => setData({ ...data, organization_name: e.target.value })} required /></label><label className="field"><span>Website (optional)</span><input type="url" value={data.website} onChange={(e) => setData({ ...data, website: e.target.value })} /></label><label className="field"><span>Your role</span><select value={data.role} onChange={(e) => setData({ ...data, role: e.target.value })} required><option value="">Select your role</option><option>Founder</option><option>Engineering</option><option>Security</option><option>Compliance</option><option>Operations</option></select></label></>}{step === 2 && <div className="choice-list">{["Agent development", "MCP security", "Production governance", "Compliance evidence", "Enterprise evaluation"].map((choice) => <label key={choice}><input type="radio" name="use-case" checked={data.use_case === choice} onChange={() => setData({ ...data, use_case: choice })} /><span>{choice}</span></label>)}</div>}{step === 3 && <><p className="configuration-note">This records a plan preference only. Paid entitlement activates only after confirmed billing and backend processing.</p><div className="choice-list">{[["FREE", "Community", "Workspace setup and currently supported developer interfaces"], ["PRO", "Pro preference", "Continue to billing availability after workspace creation"], ["ENTERPRISE", "Enterprise preference", "Continue to an enterprise evaluation path"]].map(([value, name, copy]) => <label key={value}><input type="radio" name="plan" checked={data.plan === value} onChange={() => setData({ ...data, plan: value as typeof data.plan })} /><span><strong>{name}</strong><small>{copy}</small></span></label>)}</div></>}{error && <div id="onboarding-error" className="form-error" role="alert">{error}</div>}<div className="onboarding-actions"><Button type="button" variant="secondary" disabled={step === 1 || busy} onClick={() => setStep(step - 1)}>Back</Button><Button disabled={busy}>{busy ? "Creating workspace…" : step === steps.length ? "Create workspace →" : "Continue →"}</Button></div></form><p className="draft-note">{draftAvailable ? "Draft values are kept only for this browser session until the final backend submission succeeds." : "Browser storage is unavailable. Draft values will not survive a refresh."}</p></section><aside className="onboarding-outcome"><h2>What you’ll get</h2>{[[ShieldCheck, "Verified account", "Email ownership verified before access."], [Building2, "Organization-bound workspace", "Settings and activity stay tenant-scoped."], [KeyRound, "Supported credential setup", "Credential availability follows verified identity and current backend capability. Workspace creation does not establish execution authority."]].map(([Icon, title, copy]) => { const C = Icon as typeof ShieldCheck; return <div key={String(title)}><C /><p><strong>{String(title)}</strong><span>{String(copy)}</span></p></div>; })}</aside></div></main>;
}
