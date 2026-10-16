// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { Button } from "../../components/Button";
import { ApiError } from "../../lib/api";
import { readCustomerAuthorityRecords } from "../../lib/customerAuthorityRecords";
import type { WebSession } from "../dashboard/DashboardShell";

type Records = Awaited<ReturnType<typeof readCustomerAuthorityRecords>>;
type Result = { attempt: number; organizationId: string } & ({ kind: "ready"; records: Records } | { kind: "error"; message: string; expired: boolean });

export function AuthorityRecordDetails() {
  const session = useOutletContext<WebSession>();
  const organizationId = session.organization?.id;
  const [attempt, setAttempt] = useState(-1);
  const [result, setResult] = useState<Result | null>(null);
  const current = result?.organizationId === organizationId && result?.attempt === attempt ? result : null;
  useEffect(() => {
    if (!organizationId || attempt < 0) return;
    const id = organizationId;
    const controller = new AbortController();
    let active = true;
    async function load() {
      try {
        const records = await readCustomerAuthorityRecords(id, controller.signal);
        if (active) setResult({ organizationId: id, attempt, kind: "ready", records });
      } catch (cause) {
        if (!active) return;
        const expired = cause instanceof ApiError && cause.status === 401;
        const message = expired ? "Your session has expired. Sign in again to read recorded details." : cause instanceof ApiError && cause.status === 403 ? "This session cannot read recorded details. Owner or admin membership is required." : "Recorded details could not be confirmed. No empty or valid consent state is inferred.";
        setResult({ organizationId: id, attempt, kind: "error", message, expired });
      }
    }
    void load();
    return () => { active = false; controller.abort(); };
  }, [organizationId, attempt]);
  const busy = Boolean(organizationId && attempt >= 0 && !current);
  return <section className="data-panel" aria-label="Recorded consent and root details" aria-busy={busy} style={{ overflowWrap: "anywhere" }}>
    <h2>Recorded consent and root metadata</h2>
    <p>This read shows the latest root and paired consent returned by the backend. It is not a complete consent history, a validity check, or execution permission. Recorded scope and digests require independent server verification for every action.</p>
    {!organizationId ? <p>Authenticated organization context is unavailable.</p> : attempt < 0 ? <p>No detail read has been requested.</p> : busy ? <p role="status">Loading recorded details…</p> : current?.kind === "error" ? <div role="alert"><p>{current.message}</p>{current.expired && <a href="/login?next=%2Fdashboard%2Fagents">Sign in again</a>}</div> : current?.kind === "ready" ? <>
      <p role="status">Recorded snapshot loaded. This does not establish authority or live revocation status.</p>
      {current.records.root ? <><h3>Returned root record</h3><dl className="metadata-grid">{Object.entries({ "Record ID": current.records.root.id, "Subject ID": current.records.root.subject, Issuer: current.records.root.issuer, "Root type": current.records.root.type, "Recorded verification method": current.records.root.method, "Recorded issue time": current.records.root.issuedAt, "Recorded expiry": current.records.root.expiresAt ?? "Not returned", "Recorded digest — not independently verified": current.records.root.digest }).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></> : <p>No root record was returned.</p>}
      {current.records.consent ? <><h3>Returned consent record</h3><dl className="metadata-grid">{Object.entries({ "Consent ID": current.records.consent.id, "Recorded scope": current.records.consent.scope, Purpose: current.records.consent.purpose, "Consent method": current.records.consent.method, "Recorded consent time": current.records.consent.consentedAt, "Recorded consent digest — not independently verified": current.records.consent.digest }).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl><ScopeList label="Recorded consent action types" items={current.records.consent.actionTypes} /><ScopeList label="Recorded consent targets" items={current.records.consent.targets} /></> : <p>No consent record was returned.</p>}
    </> : null}
    {organizationId && <Button variant="secondary" disabled={busy} onClick={() => setAttempt((value) => value + 1)}>{attempt < 0 ? "Read recorded consent details" : current?.kind === "error" ? "Retry detail read" : "Refresh recorded details"}</Button>}
  </section>;
}

function ScopeList({ label, items }: { label: string; items: string[] }) {
  return <div><h4>{label}</h4><p>Showing up to 10 of {items.length} returned entries. Recorded scope does not grant permission.</p><ul aria-label={label}>{items.slice(0, 10).map((item, index) => <li key={index}><code>{item}</code></li>)}</ul></div>;
}
