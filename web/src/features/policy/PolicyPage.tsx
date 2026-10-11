// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AlertTriangle, ArrowDown, ArrowUp, Plus, RotateCw, Trash2 } from "lucide-react";
import { useOutletContext } from "react-router-dom";
import { Button } from "../../components/Button";
import { api, messageFrom } from "../../lib/api";
import type { DomainRecord, LoadState } from "../../lib/contracts";
import type { WebSession } from "../dashboard/DashboardShell";

type PolicyRule = DomainRecord & {
  rule_id: string;
  reason_code: string;
  effect: string;
  risk_tiers?: string[] | null;
  action_types?: string[] | null;
  targets?: string[] | null;
};

type PolicyPayload = { org_id: string; rules: PolicyRule[]; can_edit: boolean };

const EFFECTS = ["ALLOW", "DENY", "REQUIRE_APPROVAL", "QUARANTINE"] as const;

export function PolicyPage() {
  const session = useOutletContext<WebSession>();
  const canEdit = session.organization?.role === "ADMIN" || session.organization?.role === "OWNER";
  const [state, setState] = useState<LoadState>("loading");
  const [rules, setRules] = useState<PolicyRule[]>([]);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState({ rule_id: "", reason_code: "", effect: "REQUIRE_APPROVAL", action_types: "" });

  const load = useCallback(async () => {
    setState("loading");
    setError("");
    try {
      const payload = await api<PolicyPayload>("/api/v1/web/policy");
      setRules(payload.rules);
      setState(payload.rules.length ? "success" : "empty");
    } catch (cause) {
      setError(messageFrom(cause, "Policy could not be loaded"));
      setState("error");
    }
  }, []);

  useEffect(() => {
    const task = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(task);
  }, [load]);

  async function addRule(event: FormEvent) {
    event.preventDefault();
    if (!canEdit) return;
    setError("");
    try {
      const action_types = draft.action_types.split(",").map((s) => s.trim()).filter(Boolean);
      await api("/api/v1/web/policy/rules", {
        method: "POST",
        body: JSON.stringify({
          rule_id: draft.rule_id.trim(),
          reason_code: draft.reason_code.trim(),
          effect: draft.effect,
          action_types: action_types.length ? action_types : null,
        }),
      });
      setDraft({ rule_id: "", reason_code: "", effect: "REQUIRE_APPROVAL", action_types: "" });
      await load();
    } catch (cause) {
      setError(messageFrom(cause, "Rule could not be added"));
    }
  }

  async function removeRule(ruleId: string) {
    if (!canEdit) return;
    setError("");
    try {
      await api(`/api/v1/web/policy/rules/${encodeURIComponent(ruleId)}`, { method: "DELETE" });
      await load();
    } catch (cause) {
      setError(messageFrom(cause, "Rule could not be removed"));
    }
  }

  async function moveRule(index: number, direction: -1 | 1) {
    if (!canEdit) return;
    const target = index + direction;
    if (target < 0 || target >= rules.length) return;
    const ids = rules.map((r) => String(r.rule_id));
    const next = [...ids];
    const [removed] = next.splice(index, 1);
    next.splice(target, 0, removed);
    setError("");
    try {
      const payload = await api<{ rules: PolicyRule[] }>("/api/v1/web/policy/reorder", {
        method: "POST",
        body: JSON.stringify({ rule_ids: next }),
      });
      setRules(payload.rules);
    } catch (cause) {
      setError(messageFrom(cause, "Reorder failed"));
      await load();
    }
  }

  return (
    <main className="dashboard-content">
      <div className="page-heading">
        <div>
          <h1>Policy</h1>
          <p>Ordered governance rules for this organization (first match wins).</p>
        </div>
        {!canEdit && <span>View only — administrator role required to edit</span>}
      </div>
      {error && <div className="form-error" role="alert" aria-live="assertive">{error}</div>}
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
                        <button type="button" aria-label="Move rule up" disabled={index === 0} onClick={() => void moveRule(index, -1)}><ArrowUp aria-hidden="true" /></button>
                        <button type="button" aria-label="Move rule down" disabled={index === rules.length - 1} onClick={() => void moveRule(index, 1)}><ArrowDown aria-hidden="true" /></button>
                        <button type="button" aria-label="Remove rule" onClick={() => void removeRule(String(rule.rule_id))}><Trash2 aria-hidden="true" /></button>
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
              <form onSubmit={addRule}>
                <label className="field"><span>Rule ID</span><input value={draft.rule_id} onChange={(e) => setDraft((d) => ({ ...d, rule_id: e.target.value }))} required minLength={1} /></label>
                <label className="field"><span>Reason code</span><input value={draft.reason_code} onChange={(e) => setDraft((d) => ({ ...d, reason_code: e.target.value }))} required minLength={1} /></label>
                <label className="field"><span>Effect</span>
                  <select value={draft.effect} onChange={(e) => setDraft((d) => ({ ...d, effect: e.target.value }))}>
                    {EFFECTS.map((effect) => <option key={effect} value={effect}>{effect}</option>)}
                  </select>
                </label>
                <label className="field"><span>Action types (comma-separated, optional)</span><input value={draft.action_types} onChange={(e) => setDraft((d) => ({ ...d, action_types: e.target.value }))} placeholder="rai_scan, payment.send" /></label>
                <Button><Plus aria-hidden="true" /> Add rule</Button>
              </form>
            </section>
          )}
        </>
      )}
    </main>
  );
}
