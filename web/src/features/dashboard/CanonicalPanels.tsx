// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, FileCheck2, ShieldCheck, Users, X } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { AccessibleDialog } from "../../components/AccessibleDialog";
import { Button } from "../../components/Button";
import { api, messageFrom } from "../../lib/api";
import type { ApprovalDetail, ApprovalExecutionResponse, ApprovalResolution, ConsequentialOutcome, DomainRecord, EvidenceAttestation, EvidenceVerification } from "../../lib/contracts";

type Decision = { detail: ApprovalDetail; outcome: "APPROVED" | "DENIED" };

export function ApprovalContractPanel({ records, onError, onChanged }: { records: DomainRecord[]; onError: (value: string) => void; onChanged: () => Promise<void> }) {
  const [details, setDetails] = useState<Record<string, ApprovalDetail>>({});
  const [detailErrors, setDetailErrors] = useState<Record<string, string>>({});
  const [confirm, setConfirm] = useState<Decision | null>(null);
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<ConsequentialOutcome | null>(null);
  const close = useCallback(() => setConfirm(null), []);

  const loadDetail = useCallback(async (id: string) => {
    try {
      const detail = await api<ApprovalDetail>(`/api/v1/web/approvals/${id}`);
      setDetails((current) => ({ ...current, [id]: detail }));
      setDetailErrors((current) => { const next = { ...current }; delete next[id]; return next; });
      return detail;
    } catch (cause) {
      setDetailErrors((current) => ({ ...current, [id]: messageFrom(cause, "Approval detail could not be loaded") }));
      return null;
    }
  }, []);

  useEffect(() => {
    const task = window.setTimeout(() => {
      for (const record of records) {
        const id = String(record.approval_id ?? "");
        if (id) void loadDetail(id);
      }
    }, 0);
    return () => window.clearTimeout(task);
  }, [loadDetail, records]);

  async function decide() {
    if (!confirm) return;
    const { detail, outcome: requested } = confirm;
    const id = detail.approval_id;
    setBusy(true); onError(""); setOutcome(null);
    try {
      const resolved = await api<ApprovalResolution>(`/api/v1/web/approvals/${id}/resolve`, { method: "POST", body: JSON.stringify({ outcome: requested }) });
      const refreshed = await loadDetail(id);
      if (requested === "DENIED") {
        setOutcome({ state: "DENIED", approvalId: id }); setConfirm(null); await onChanged(); return;
      }
      if (resolved.status !== "APPROVED") {
        setOutcome({ state: "PENDING", approvalId: id, recorded: refreshed?.current_vote_count ?? detail.current_vote_count + 1, required: refreshed?.required_approvals ?? detail.required_approvals });
        setConfirm(null); await onChanged(); return;
      }
      const executed = await api<ApprovalExecutionResponse>(`/api/v1/web/approvals/${id}/execute`, { method: "POST", body: JSON.stringify({}) });
      if (executed.execution_status === "UNKNOWN") {
        setOutcome({ state: "UNKNOWN", approvalId: id, message: executed.message, reconciliationRequired: executed.reconciliation_required, evidenceId: executed.evidence_id ?? undefined, outcomeId: executed.outcome_id ?? undefined });
        setConfirm(null); return;
      }
      if (executed.execution_status === "SUCCEEDED") {
        setOutcome({ state: "SUCCESS", approvalId: id, message: executed.message, evidenceId: executed.evidence_id ?? undefined, outcomeId: executed.outcome_id ?? undefined });
        setConfirm(null); await onChanged(); return;
      }
      setOutcome({ state: "FAILED", approvalId: id, message: executed.message }); setConfirm(null);
    } catch (cause) {
      setOutcome({ state: "FAILED", approvalId: id, message: messageFrom(cause, "Approval could not be submitted") }); setConfirm(null);
    } finally { setBusy(false); }
  }

  if (!records.length && !outcome) return <Empty title="No approvals are waiting" />;
  return <>
    {outcome && <ExecutionNotice outcome={outcome} />}
    <section className="data-panel approval-list">
      {records.map((record) => {
        const id = String(record.approval_id ?? "");
        const detail = details[id];
        if (!detail) return <article className="approval-card" key={id}><h2>{String(record.action_type ?? "Approval request")}</h2>{detailErrors[id] ? <><p role="alert">{detailErrors[id]}</p><Button variant="secondary" onClick={() => void loadDetail(id)}>Retry detail</Button></> : <p role="status">Loading canonical approval detail…</p>}</article>;
        const progress = `${detail.current_vote_count} of ${detail.required_approvals}`;
        return <article key={id} className="approval-card">
          <header><div><h2>{detail.action_type}</h2><p className="quorum-progress" aria-label={`${progress} required approvals recorded`}>{progress} approvals</p></div><span>{detail.status}</span></header>
          <dl>
            <Row label="Approval ID" value={detail.approval_id} code />
            <Row label="Target" value={detail.target} />
            <Row label="Risk" value={detail.risk_tier} />
            <Row label="Requester" value={detail.requester ?? detail.requested_by} />
            <Row label="Purpose" value={detail.purpose} />
            <Row label="Execution state" value={detail.execution_state} />
            {detail.argument_summary && <Row label="Safe argument summary" value={`${detail.argument_summary.argument_count} arguments: ${detail.argument_summary.argument_keys.join(", ")}`} />}
          </dl>
          <section className="vote-history" aria-label="Approval vote history"><h3>Vote history</h3>{detail.votes.length ? <ol>{detail.votes.map((vote) => <li key={vote.vote_id}><strong>{vote.outcome}</strong><span>Authorized reviewer {vote.resolver_identity_id}</span><time>{vote.resolved_at}</time></li>)}</ol> : <p>No votes recorded.</p>}</section>
          <div className="approval-actions"><Button disabled={busy || detail.status !== "PENDING"} onClick={() => setConfirm({ detail, outcome: "APPROVED" })}>Approve</Button><Button variant="danger" disabled={busy || detail.status !== "PENDING"} onClick={() => setConfirm({ detail, outcome: "DENIED" })}>Deny</Button></div>
        </article>;
      })}
    </section>
    {confirm && <AccessibleDialog labelId="approval-contract-confirm-title" onClose={close}><header><div><h2 id="approval-contract-confirm-title">{confirm.outcome === "APPROVED" ? "Approve" : "Deny"} this request?</h2><p>{confirm.detail.action_type} → {confirm.detail.target}</p></div><button onClick={close} aria-label="Close"><X aria-hidden="true" /></button></header><p>This records one backend vote. It does not create execution authority in the browser.</p><div className="modal-actions"><Button variant={confirm.outcome === "DENIED" ? "danger" : "primary"} disabled={busy} onClick={() => void decide()}>{busy ? "Submitting…" : `Confirm ${confirm.outcome.toLowerCase()}`}</Button><Button variant="secondary" disabled={busy} onClick={close}>Cancel</Button></div></AccessibleDialog>}
  </>;
}

function ExecutionNotice({ outcome }: { outcome: ConsequentialOutcome }) {
  if (outcome.state === "UNKNOWN") return <section className="outcome-notice outcome-notice--unknown" role="alert" aria-live="assertive"><AlertTriangle aria-hidden="true" /><div><h2>Execution outcome is uncertain</h2><p>{outcome.message}</p>{outcome.reconciliationRequired && <strong>Reconciliation required</strong>}{outcome.evidenceId && <p>Evidence ID: <code>{outcome.evidenceId}</code></p>}{outcome.outcomeId && <p>Outcome ID: <code>{outcome.outcomeId}</code></p>}<p>Do not retry. Inspect evidence before taking further action.</p>{outcome.evidenceId && <Link to={`/dashboard/evidence?evidence=${encodeURIComponent(outcome.evidenceId)}`}>View evidence</Link>}</div></section>;
  if (outcome.state === "SUCCESS") return <section className="outcome-notice outcome-notice--success" role="status"><CheckCircle2 aria-hidden="true" /><div><h2>Execution succeeded</h2><p>{outcome.message}</p>{outcome.evidenceId && <Link to={`/dashboard/evidence?evidence=${encodeURIComponent(outcome.evidenceId)}`}>View evidence</Link>}</div></section>;
  if (outcome.state === "PENDING") return <section className="outcome-notice" role="status" aria-live="polite"><Users aria-hidden="true" /><div><h2>{outcome.recorded} of {outcome.required} approvals recorded</h2><p>Waiting for another authorized approver. No execution has started.</p></div></section>;
  if (outcome.state === "DENIED") return <section className="outcome-notice" role="status"><ShieldCheck aria-hidden="true" /><div><h2>Request denied</h2><p>No execution was requested.</p></div></section>;
  return <section className="outcome-notice outcome-notice--error" role="alert"><AlertTriangle aria-hidden="true" /><div><h2>Request could not be completed</h2><p>{outcome.message}</p></div></section>;
}

export function EvidenceContractPanel({ records }: { records: DomainRecord[] }) {
  const [params] = useSearchParams();
  const requestedEvidenceId = params.get("evidence");
  const [query, setQuery] = useState("");
  const [decision, setDecision] = useState("");
  const [items, setItems] = useState(records);
  const [selected, setSelected] = useState<DomainRecord | null>(null);
  const [attestation, setAttestation] = useState<EvidenceAttestation | null>(null);
  const [verification, setVerification] = useState<EvidenceVerification | null>(null);
  const [error, setError] = useState("");
  const close = useCallback(() => { setSelected(null); setAttestation(null); }, []);

  const openEvidence = useCallback(async (id: string) => {
    setError("");
    try {
      const [detail, attested] = await Promise.all([
        api<DomainRecord>(`/api/v1/web/evidence/${encodeURIComponent(id)}`),
        api<EvidenceAttestation>(`/api/v1/web/evidence/${encodeURIComponent(id)}/attestation`),
      ]);
      setSelected(detail); setAttestation(attested);
    } catch (cause) { setError(messageFrom(cause, "Evidence detail could not be loaded")); }
  }, []);

  useEffect(() => { setItems(records); }, [records]);
  useEffect(() => { const task = window.setTimeout(() => void api<EvidenceVerification>("/api/v1/web/evidence/verify").then(setVerification).catch((cause) => setError(messageFrom(cause, "Evidence verification could not be loaded"))), 0); return () => window.clearTimeout(task); }, []);
  useEffect(() => { if (requestedEvidenceId) { const task = window.setTimeout(() => void openEvidence(requestedEvidenceId), 0); return () => window.clearTimeout(task); } }, [openEvidence, requestedEvidenceId]);

  async function filterDecision(next: string) {
    setDecision(next); setError("");
    try { const suffix = next ? `&decision=${encodeURIComponent(next)}` : ""; const response = await api<{ evidence: DomainRecord[] }>(`/api/v1/web/evidence?limit=50${suffix}`); setItems(response.evidence); }
    catch (cause) { setError(messageFrom(cause, "Evidence list could not be filtered")); }
  }
  const filtered = useMemo(() => items.filter((record) => [record.evidence_id, record.agent_id, record.identity_id, record.action_type, record.target, record.decision].some((value) => String(value ?? "").toLowerCase().includes(query.toLowerCase()))), [items, query]);
  return <>
    {error && <div className="form-error" role="alert">{error}</div>}
    <section className="data-panel evidence-verification"><header><div><h2>Evidence chain</h2><p>WhitePact evidence is hash-chained under the documented verification boundary.</p></div>{verification && <strong className={`posture posture--${verification.status === "VALID" ? "configured" : "missing"}`}>{verification.status}</strong>}</header>{verification && <><p>{verification.integrity_note}</p><dl><Row label="Chain intact" value={verification.chain_intact ? "Yes" : "No"} /><Row label="Cryptographically signed" value="No" /></dl>{verification.status === "INCOMPLETE" && <p className="configuration-note">The chain hashes correctly but contains legacy pre-canonical entries; it is not presented as fully verified.</p>}</>}</section>
    <section className="data-panel evidence-ledger"><header><div><h2>Bounded evidence list</h2><p>Up to 50 records are returned. This is not full pagination.</p></div><div><label className="field compact-field"><span>Decision</span><select value={decision} onChange={(event) => void filterDecision(event.target.value)}><option value="">All returned decisions</option><option value="ALLOW">Allow</option><option value="DENY">Deny</option><option value="REQUIRE_APPROVAL">Require approval</option></select></label><label className="field compact-field"><span>Filter loaded records</span><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} /></label></div></header>
      <div className="evidence-cards">{filtered.map((record, index) => <article key={String(record.evidence_id ?? index)}><div><span className={`decision decision--${String(record.decision ?? "").toLowerCase().replaceAll("_", "-")}`}>{value(record.decision)}</span><time>{value(record.recorded_at ?? record.evaluated_at)}</time></div><h2>{value(record.action_type)}</h2><dl><Row label="Actor" value={record.agent_id ?? record.identity_id} /><Row label="Target" value={record.target ?? record.execution_target} /><Row label="Evidence ID" value={record.evidence_id} code /><Row label="Integrity" value={record.integrity_status} /></dl><Button variant="secondary" onClick={() => void openEvidence(String(record.evidence_id))}>View evidence</Button></article>)}</div>
      {!filtered.length && <Empty title="No evidence records match" />}
    </section>
    {selected && <AccessibleDialog labelId="evidence-contract-title" onClose={close} className="evidence-detail"><header><div><h2 id="evidence-contract-title">Evidence details</h2><p>{value(selected.evidence_id)}</p></div><button onClick={close} aria-label="Close"><X aria-hidden="true" /></button></header><section><h3>Decision evidence</h3><dl>{["evidence_id", "agent_id", "identity_id", "action_type", "target", "purpose", "risk_tier", "policy_version", "decision", "reason_codes", "approval_id", "execution_authorization_id", "evaluated_at", "recorded_at", "prev_hash", "hash"].filter((key) => selected[key] !== null && selected[key] !== undefined).map((key) => <Row key={key} label={key.replaceAll("_", " ")} value={selected[key]} code={key.includes("id") || key.includes("hash")} />)}</dl></section>{attestation && <section className={attestation.outcome_status === "UNKNOWN" ? "attestation attestation--unknown" : "attestation"}><h3>Evidence attestation</h3><p>Not cryptographically signed. Integrity is established by linkage to the evidence hash chain.</p><dl><Row label="Decision" value={attestation.decision} /><Row label="Outcome" value={attestation.outcome_status} /><Row label="Reconciliation" value={attestation.reconciliation_status} /><Row label="Evidence hash" value={attestation.evidence_hash} code /></dl>{attestation.outcome_status === "UNKNOWN" && <strong>Reconciliation required</strong>}</section>}</AccessibleDialog>}
  </>;
}

function Row({ label, value: raw, code = false }: { label: string; value: unknown; code?: boolean }) { return <div><dt>{label}</dt><dd>{code ? <code>{value(raw)}</code> : value(raw)}</dd></div>; }
function value(raw: unknown) { if (Array.isArray(raw)) return raw.join(", "); if (raw === null || raw === undefined || raw === "") return "—"; if (typeof raw === "object") return JSON.stringify(raw); return String(raw); }
function Empty({ title }: { title: string }) { return <div className="empty-state"><FileCheck2 aria-hidden="true" /><h3>{title}</h3></div>; }
