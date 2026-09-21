// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { FormEvent, useEffect, useState } from "react";
import { ArrowRight, Building2, CreditCard, FileCheck2, ShieldCheck, Users } from "lucide-react";
import { Link, useOutletContext, useParams } from "react-router-dom";
import { Button } from "../../components/Button";
import { api, ApiError } from "../../lib/api";
import type { WebSession } from "./DashboardShell";

type RecordValue = string | number | boolean | null | string[];
type DomainRecord = Record<string, RecordValue>;
type DomainResponse = { items: DomainRecord[]; source: string; billing_configured?: boolean };
const supported = {
  approvals: { title: "Approvals", copy: "Requests waiting for an authorized human decision.", icon: Users },
  evidence: { title: "Evidence", copy: "Tenant-scoped, hash-chained governance decision records.", icon: FileCheck2 },
  organization: { title: "Organization", copy: "Workspace identity, ownership and plan metadata.", icon: Building2 },
  members: { title: "Members", copy: "Verified people and enforced roles in this organization.", icon: Users },
  billing: { title: "Billing", copy: "Subscription state and entitlement management. This page is not a usage meter.", icon: CreditCard },
  security: { title: "Security", copy: "Security posture loaded from backend identity stores for this workspace.", icon: ShieldCheck },
} as const;

export function DomainPage() {
  const { domain = "" } = useParams();
  const key = domain in supported ? domain as keyof typeof supported : "security";
  const config = supported[key];
  const [result, setResult] = useState<DomainResponse>(() => ({ items: [], source: "loading" }));
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const session = useOutletContext<WebSession>();
  const Icon = config.icon;

  async function load() {
    try {
      const value = await api<DomainResponse>(`/api/v1/web/dashboard/${key}`);
      setResult(value);
      if (key === "organization") setName(String(value.items[0]?.name ?? ""));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load this section");
    }
  }

  useEffect(() => {
    setError("");
    void load();
  }, [key]);

  async function startBilling(plan: "PRO" | "ENTERPRISE") { setError(""); try { const value = await api<{ checkout_url: string }>("/api/v1/web/billing/checkout", { method: "POST", body: JSON.stringify({ plan }) }); window.location.assign(value.checkout_url); } catch (cause) { setError(cause instanceof Error ? cause.message : "Billing could not be started"); } }
  async function openPortal() { setError(""); try { const value = await api<{ portal_url: string }>("/api/v1/web/billing/portal", { method: "POST", body: JSON.stringify({ return_url: `${window.location.origin}/dashboard/billing` }) }); window.location.assign(value.portal_url); } catch (cause) { setError(cause instanceof Error ? cause.message : "Billing portal could not be opened"); } }
  async function saveOrg(event: FormEvent) { event.preventDefault(); setError(""); try { await api("/api/v1/web/organization", { method: "PATCH", body: JSON.stringify({ name }) }); setResult((current) => ({ ...current, items: current.items.map((item, index) => index === 0 ? { ...item, name } : item) })); } catch (cause) { setError(cause instanceof Error ? cause.message : "Organization could not be updated"); } }

  const emptyCopy = key === "approvals" ? "No requests are waiting for approval." : key === "evidence" ? "No governed activity yet. Connect your first agent and WhitePact will begin evaluating runtime actions." : "No records are available.";
  return <main className="dashboard-content"><div className="page-heading"><div><h1>{config.title}</h1><p>{config.copy}</p></div>{key === "billing" && <span>{session.organization?.plan ?? "FREE"} plan</span>}</div>{error && <div className="form-error" role="alert">{error}</div>}
    {key === "security" ? <SecurityCards items={result.items} source={result.source} /> : key === "billing" ? <BillingPanel item={result.items[0]} configured={Boolean(result.billing_configured)} onCheckout={startBilling} onPortal={openPortal} /> : key === "organization" && result.items[0] ? <section className="data-panel settings-panel"><form onSubmit={saveOrg}><label className="field"><span>Organization name</span><input value={name} onChange={(event)=>setName(event.target.value)} required minLength={2} /></label><div className="metadata-grid"><p><span>Organization ID</span><code>{String(result.items[0].id)}</code></p><p><span>Slug</span><strong>{String(result.items[0].slug)}</strong></p><p><span>Owner</span><strong>{session.user.full_name}</strong></p><p><span>Plan</span><strong>{String(result.items[0].plan)}</strong></p></div><Button>Save organization</Button></form></section> : key === "members" ? <MembersPanel records={result.items} onError={setError} onInvited={load} /> : key === "approvals" ? <ApprovalsPanel records={result.items} onError={setError} onChanged={load} /> : result.items.length ? <RecordTable records={result.items} domain={key} /> : <section className="data-panel"><div className="empty-state"><Icon /><h2>No {config.title.toLowerCase()} yet</h2><p>{emptyCopy}</p>{key === "evidence" && <Link to="/dashboard/api-keys">Create an API key <ArrowRight /></Link>}</div></section>}
  </main>;
}

function SecurityCards({ items, source }: { items: DomainRecord[]; source: string }) {
  if (!items.length) {
    return <section className="security-cards"><article><ShieldCheck /><h2>Security state</h2><p>UNAVAILABLE. Backend security state has not been returned.</p><small>source: {source}</small></article></section>;
  }
  return <section className="security-cards">{items.map((item) => <article key={String(item.title)}><ShieldCheck /><h2>{format(item.title)}</h2><p data-testid={`security-status-${String(item.title).toLowerCase().replaceAll(" ", "-")}`}>{format(item.status)}</p><p>{format(item.detail)}</p><small>source: {format(item.source)}</small></article>)}</section>;
}

function ApprovalsPanel({ records, onError, onChanged }: { records: DomainRecord[]; onError: (value: string) => void; onChanged: () => void }) {
  const [busy, setBusy] = useState<string>("");
  async function decide(approvalId: string, outcome: "APPROVED" | "DENIED") {
    setBusy(`${approvalId}:${outcome}`);
    onError("");
    try {
      const resolved = await api<{ status: string; required_approvals?: number }>(`/api/v1/web/approvals/${approvalId}/resolve`, { method: "POST", body: JSON.stringify({ outcome }) });
      if (outcome === "APPROVED" && resolved.status === "APPROVED") {
        await api(`/api/v1/web/approvals/${approvalId}/execute`, { method: "POST", body: JSON.stringify({}) });
      }
      onChanged();
    } catch (cause) {
      onError(cause instanceof ApiError || cause instanceof Error ? cause.message : "Approval could not be submitted");
    } finally {
      setBusy("");
    }
  }
  if (!records.length) {
    return <section className="data-panel"><div className="empty-state"><Users /><h2>No approvals yet</h2><p>No requests are waiting for approval.</p></div></section>;
  }
  return <section className="data-panel approval-list">{records.map((record) => {
    const id = String(record.approval_id ?? "");
    const status = String(record.status ?? "PENDING");
    const closed = status !== "PENDING";
    return <article key={id} className="approval-card" data-testid={`approval-${id}`}>
      <header><h2>{format(record.action_type)}</h2><span>{status}</span></header>
      <dl>
        <div><dt>Approval ID</dt><dd>{id}</dd></div>
        <div><dt>Target</dt><dd>{format(record.target)}</dd></div>
        <div><dt>Risk</dt><dd>{format(record.risk_tier)}</dd></div>
        <div><dt>Required approvals</dt><dd>{format(record.required_approvals)}</dd></div>
        <div><dt>Requested</dt><dd>{format(record.requested_at)}</dd></div>
        <div><dt>Requested by</dt><dd>{format(record.requested_by)}</dd></div>
      </dl>
      <div className="approval-actions">
        <Button disabled={closed || Boolean(busy)} onClick={() => void decide(id, "APPROVED")}>{busy === `${id}:APPROVED` ? "Approving…" : "Approve"}</Button>
        <Button variant="danger" disabled={closed || Boolean(busy)} onClick={() => void decide(id, "DENIED")}>{busy === `${id}:DENIED` ? "Denying…" : "Deny"}</Button>
      </div>
      <p className="configuration-note">These controls invoke the canonical backend approval path. They do not mint execution authority in the browser.</p>
    </article>;
  })}</section>;
}

function MembersPanel({ records, onError, onInvited }: { records: DomainRecord[]; onError: (value: string) => void; onInvited: () => void }) {
  const [email, setEmail] = useState("");
    const [role, setRole] = useState("VIEWER");
  const [busy, setBusy] = useState(false);
  async function invite(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    onError("");
    try {
      await api("/api/v1/web/invitations", { method: "POST", body: JSON.stringify({ email, role }) });
      setEmail("");
      onInvited();
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : "Invitation could not be sent");
    } finally {
      setBusy(false);
    }
  }
  return <>
    <section className="data-panel settings-panel"><form onSubmit={invite}><h2>Invite a member</h2><label className="field"><span>Email</span><input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label><label className="field"><span>Role</span><select value={role} onChange={(event) => setRole(event.target.value)}><option value="ADMIN">Admin</option><option value="ANALYST">Analyst</option><option value="VIEWER">Viewer</option></select></label><Button disabled={busy}>{busy ? "Sending…" : "Send invitation"}</Button></form></section>
    {records.length ? <RecordTable records={records} domain="members" /> : <section className="data-panel"><div className="empty-state"><Users /><h2>No members yet</h2><p>No records are available.</p></div></section>}
  </>;
}

function RecordTable({ records, domain }: { records: DomainRecord[]; domain: string }) { const fields = domain === "members" ? ["full_name","email","role","joined_at"] : domain === "approvals" ? ["approval_id","action_type","risk_tier","status","requested_at"] : ["evidence_id","agent_id","action_type","risk_tier","decision","recorded_at"]; return <section className="data-panel"><div className="record-table" role="table" aria-label={`${domain} records`}><div role="row" className="record-row record-head">{fields.map(field=><span role="columnheader" key={field}>{field.replaceAll("_", " ")}</span>)}</div>{records.map((record,index)=><div role="row" className="record-row" key={String(record.id ?? record.approval_id ?? record.evidence_id ?? index)}>{fields.map(field=><span role="cell" key={field}>{format(record[field])}</span>)}</div>)}</div></section>; }
function format(value: RecordValue | undefined) { if (Array.isArray(value)) return value.join(", "); if (value === null || value === undefined || value === "") return "—"; return String(value); }
function BillingPanel({ item, configured, onCheckout, onPortal }: { item?: DomainRecord; configured: boolean; onCheckout: (plan: "PRO"|"ENTERPRISE")=>void; onPortal: ()=>void }) { const plan=String(item?.plan ?? "FREE"), status=String(item?.subscription_status ?? "inactive"), customer=Boolean(item?.stripe_customer_id); return <section className="billing-panel"><article><span>Current plan</span><strong>{plan}</strong><p>Subscription status: {status}</p>{item?.plan_renews_at && <p>Renews or changes: {String(item.plan_renews_at)}</p>}</article><article><span>Billing connection</span><strong>{configured ? "Available" : "Not configured"}</strong><p>Access changes only after a signed Stripe webhook is processed. WhitePact V1 does not expose a customer usage meter on this page.</p></article><div className="billing-actions">{plan !== "PRO" && <Button onClick={()=>onCheckout("PRO")} disabled={!configured}>Choose Pro</Button>}{plan !== "ENTERPRISE" && <Button onClick={()=>onCheckout("ENTERPRISE")} disabled={!configured}>Choose Enterprise</Button>}{customer && <Button variant="secondary" onClick={onPortal}>Manage, downgrade or cancel</Button>}</div>{!configured && <p className="configuration-note">Billing is not configured on this deployment. No paid entitlement is being advertised as active.</p>}</section>; }
