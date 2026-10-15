// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, ArrowDown, ArrowUp, Plus, RotateCw, Trash2 } from "lucide-react";
import { useOutletContext } from "react-router-dom";
import { Button } from "../../components/Button";
import { AccessibleDialog } from "../../components/AccessibleDialog";
import { api, ApiError } from "../../lib/api";
import { mutationAcknowledgementUncertain } from "../../lib/approvalOutcome";
import type { DomainRecord, LoadState } from "../../lib/contracts";
import type { WebSession } from "../dashboard/DashboardShell";
import { PolicyHistory } from "./PolicyHistory";

type PolicyRule = DomainRecord & {
  rule_id: string;
  reason_code: string;
  effect: string;
  risk_tiers?: string[] | null;
  action_types?: string[] | null;
  targets?: string[] | null;
};

type PolicyPayload = { org_id: string; rules: PolicyRule[]; can_edit: boolean };

function canonicalRules(value: unknown): value is PolicyRule[] {
  return Array.isArray(value) && value.every((rule) => rule && typeof rule === "object" && typeof rule.rule_id === "string" && typeof rule.reason_code === "string" && typeof rule.effect === "string" && (rule.action_types == null || (Array.isArray(rule.action_types) && rule.action_types.every((action: unknown) => typeof action === "string")))) && new Set(value.map((rule) => rule.rule_id)).size === value.length;
}
function policyError(cause: unknown): string {
  if (cause instanceof ApiError && cause.status === 403) return "Policy access is not permitted. The server may require a verified step-up or another authorized reviewer.";
  if (cause instanceof ApiError && cause.status === 409) return "The policy change conflicts with current server state. Reload canonical policy before deciding what to do next.";
  if (cause instanceof ApiError && cause.status === 422) return "The server rejected this rule or ordering. Review the supported effects and rule constraints.";
  return "Policy could not be confirmed. No successful change is claimed.";
}

// Runtime redaction/quarantine decisions are valid, but the current PolicyRule
// constructor does not support creating either as an ordered policy rule.
const EFFECTS = ["ALLOW", "DENY", "REQUIRE_APPROVAL"] as const;

export function PolicyPage() {
  const session = useOutletContext<WebSession>();
  const admin = session.organization?.role === "ADMIN" || session.organization?.role === "OWNER";
  const [serverCanEdit, setServerCanEdit] = useState(false);
  const canEdit = admin && serverCanEdit;
  const [state, setState] = useState<LoadState>("loading");
  const [rules, setRules] = useState<PolicyRule[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [remove, setRemove] = useState<string | null>(null);
  const submitting = useRef(false);
  const close = useCallback(() => { if (!submitting.current) setRemove(null); }, []);
  const [draft, setDraft] = useState({ rule_id: "", reason_code: "", effect: "REQUIRE_APPROVAL", action_types: "" });

  const load = useCallback(async () => {
    setState("loading");
    setError("");
    try {
      const payload = await api<PolicyPayload>("/api/v1/web/policy");
      if (!payload || !canonicalRules(payload.rules) || typeof payload.can_edit !== "boolean") throw new Error("Invalid policy acknowledgement");
      setRules(payload.rules);
      setServerCanEdit(payload.can_edit);
      setUncertain(false);
      setState(payload.rules.length ? "success" : "empty");
    } catch (cause) {
      setServerCanEdit(false);
      setError(policyError(cause));
      setState("error");
    }
  }, []);

  useEffect(() => {
    const task = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(task);
  }, [load]);

  async function mutate(task: () => Promise<void>) {
    if (!canEdit || submitting.current || uncertain) return;
    submitting.current = true; setBusy(true); setError("");
    try { await task(); setRemove(null); await load(); }
    catch (cause) {
      if (mutationAcknowledgementUncertain(cause)) setUncertain(true);
      else setError(policyError(cause));
      setRemove(null);
    } finally { submitting.current = false; setBusy(false); }
  }

  async function addRule(event: FormEvent) {
    event.preventDefault();
    if (!canEdit || !EFFECTS.some((effect) => effect === draft.effect)) return;
    await mutate(async () => {
      const action_types = draft.action_types.split(",").map((s) => s.trim()).filter(Boolean);
      const created = await api<PolicyRule>("/api/v1/web/policy/rules", {
        method: "POST",
        body: JSON.stringify({
          rule_id: draft.rule_id.trim(),
          reason_code: draft.reason_code.trim(),
          effect: draft.effect,
          action_types: action_types.length ? action_types : null,
        }),
      });
      if (!created || created.rule_id !== draft.rule_id.trim() || created.effect !== draft.effect) throw new Error("Unconfirmed policy mutation");
      setDraft({ rule_id: "", reason_code: "", effect: "REQUIRE_APPROVAL", action_types: "" });
    });
  }

  async function removeRule(ruleId: string) {
    if (!canEdit) return;
    if (!ruleId || ruleId === "." || ruleId === "..") { setError("Invalid rule reference"); return; }
    await mutate(async () => {
      const removed = await api<{status: string; rule_id: string}>(`/api/v1/web/policy/rules/${encodeURIComponent(ruleId)}`, { method: "DELETE" });
      if (!removed || removed.status !== "removed" || removed.rule_id !== ruleId) throw new Error("Unconfirmed removal");
    });
  }

  async function moveRule(index: number, direction: -1 | 1) {
    if (!canEdit) return;
    const target = index + direction;
    if (target < 0 || target >= rules.length) return;
    const ids = rules.map((r) => String(r.rule_id));
    const next = [...ids];
    const [removed] = next.splice(index, 1);
    next.splice(target, 0, removed);
    await mutate(async () => {
      const payload = await api<{ rules: PolicyRule[] }>("/api/v1/web/policy/reorder", {
        method: "POST",
        body: JSON.stringify({ rule_ids: next }),
      });
      if (!payload || !canonicalRules(payload.rules) || JSON.stringify(payload.rules.map((rule) => rule.rule_id)) !== JSON.stringify(next)) throw new Error("Unconfirmed reorder");
    });
  }

  return (
    <main className="dashboard-content policy-page">
      <div className="page-heading">
        <div>
          <h1>Policy</h1>
          <p>Ordered governance rules for this organization (first match wins).</p>
        </div>
        {!canEdit && <span>View only — current server permission and administrator role required to edit</span>}
      </div>
      {error && <div className="form-error" role="alert" aria-live="assertive">{error}</div>}
      {admin && <PolicyHistory />}
      {uncertain && <section className="outcome-notice outcome-notice--unknown" role="alert"><h2>Policy change outcome is uncertain</h2><p>The server may have recorded the change. Do not submit it again without inspecting canonical policy. No automatic mutation retry is performed.</p><Button variant="secondary" disabled={busy} onClick={() => void load()}>Reload canonical policy</Button></section>}
      {state === "loading" ? (
        <section className="data-panel console-state" role="status"><RotateCw className="spin" aria-hidden="true" /><h2>Loading policy…</h2></section>
      ) : state === "error" ? (
        <section className="data-panel console-state"><AlertTriangle aria-hidden="true" /><h2>Policy unavailable</h2><Button variant="secondary" onClick={() => void load()}>Retry</Button></section>
      ) : (
        <>
          <section className="data-panel">
            <h2>Effective rules</h2>
            {rules.length === 0 ? <p>No rules configured yet.</p> : (
              <ol className="policy-rule-list">
                {rules.map((rule, index) => (
                  <li key={String(rule.rule_id)}>
                    <div>
                      <strong>{String(rule.rule_id)}</strong>
                      <span>{String(rule.effect)}</span>
                      <small>{String(rule.reason_code)}</small>
                      {rule.action_types && <code>{(rule.action_types as string[]).join(", ")}</code>}
                    </div>
                    {canEdit && (
                      <div className="policy-rule-actions">
                        <button type="button" aria-label="Move rule up" disabled={busy || uncertain || index === 0} onClick={() => void moveRule(index, -1)}><ArrowUp aria-hidden="true" /></button>
                        <button type="button" aria-label="Move rule down" disabled={busy || uncertain || index === rules.length - 1} onClick={() => void moveRule(index, 1)}><ArrowDown aria-hidden="true" /></button>
                        <button type="button" aria-label="Remove rule" disabled={busy || uncertain} onClick={() => setRemove(String(rule.rule_id))}><Trash2 aria-hidden="true" /></button>
                      </div>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </section>
          {canEdit && (
            <section className="data-panel settings-panel">
              <h2>Add rule</h2>
              <p>The server controls policy changes. Step-up and second-reviewer ceremonies, when required by this deployment, are not completed by this form.</p>
              <form onSubmit={addRule}>
                <fieldset disabled={busy || uncertain}>
                <label className="field"><span>Rule ID</span><input value={draft.rule_id} onChange={(e) => setDraft((d) => ({ ...d, rule_id: e.target.value }))} required minLength={1} /></label>
                <label className="field"><span>Reason code</span><input value={draft.reason_code} onChange={(e) => setDraft((d) => ({ ...d, reason_code: e.target.value }))} required minLength={1} /></label>
                <label className="field"><span>Effect</span>
                  <select aria-describedby="policy-effect-scope" value={draft.effect} onChange={(e) => setDraft((d) => ({ ...d, effect: e.target.value }))}>
                    {EFFECTS.map((effect) => <option key={effect} value={effect}>{effect}</option>)}
                  </select>
                </label>
                <small id="policy-effect-scope">Redaction and quarantine are runtime outcomes, not editable rule effects in the current policy contract.</small>
                <label className="field"><span>Action types (comma-separated, optional)</span><input value={draft.action_types} onChange={(e) => setDraft((d) => ({ ...d, action_types: e.target.value }))} placeholder="rai_scan, payment.send" /></label>
                <Button disabled={busy || uncertain}><Plus aria-hidden="true" />{busy ? "Submitting…" : "Add rule"}</Button>
                </fieldset>
              </form>
            </section>
          )}
        </>
      )}
      {remove && <AccessibleDialog labelId="policy-remove-title" onClose={close}><h2 id="policy-remove-title">Remove policy rule?</h2><p>Rule <code>{remove}</code> will be removed from the ordered policy if the server permits this change. Removing a restriction can change future governance decisions.</p><div className="modal-actions"><Button variant="danger" disabled={busy} onClick={() => void removeRule(remove)}>{busy ? "Submitting…" : "Confirm removal"}</Button><Button variant="secondary" disabled={busy} onClick={close}>Cancel</Button></div></AccessibleDialog>}
    </main>
  );
}
