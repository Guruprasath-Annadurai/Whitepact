// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { FormEvent, useEffect, useState } from "react";
import { ArrowRight, Building2, CreditCard, FileCheck2, ShieldCheck, Users } from "lucide-react";
import { Link, useOutletContext, useParams } from "react-router-dom";
import { Button } from "../../components/Button";
import { api } from "../../lib/api";
import type { WebSession } from "./DashboardShell";

type RecordValue = string | number | boolean | null | string[];
type DomainRecord = Record<string, RecordValue>;
type DomainResponse = { items: DomainRecord[]; source: string; billing_configured?: boolean };
const supported = {
  approvals: { title: "Approvals", copy: "Requests waiting for an authorized human decision.", icon: Users },
  evidence: { title: "Evidence", copy: "Tenant-scoped, hash-chained governance decision records.", icon: FileCheck2 },
  organization: { title: "Organization", copy: "Workspace identity, ownership and plan metadata.", icon: Building2 },
  members: { title: "Members", copy: "Verified people and enforced roles in this organization.", icon: Users },
  billing: { title: "Billing", copy: "Subscription state and entitlement management.", icon: CreditCard },
  security: { title: "Security", copy: "Security posture for this browser workspace and its machine credentials.", icon: ShieldCheck },
} as const;

export function DomainPage() {
  const { domain = "" } = useParams();
  const key = domain in supported ? domain as keyof typeof supported : "security";
  const config = supported[key];
  const [result, setResult] = useState<DomainResponse>(() => ({ items: [], source: key === "security" ? "local-security-controls" : "loading" }));
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const session = useOutletContext<WebSession>();
  const Icon = config.icon;
  useEffect(() => {
    if (key === "security") return;
    api<DomainResponse>(`/api/v1/web/dashboard/${key}`).then((value) => { setResult(value); if (key === "organization") setName(String(value.items[0]?.name ?? "")); }).catch((cause) => setError(cause instanceof Error ? cause.message : "Could not load this section"));
  }, [key]);

  async function startBilling(plan: "PRO" | "ENTERPRISE") { setError(""); try { const value = await api<{ checkout_url: string }>("/api/v1/web/billing/checkout", { method: "POST", body: JSON.stringify({ plan }) }); window.location.assign(value.checkout_url); } catch (cause) { setError(cause instanceof Error ? cause.message : "Billing could not be started"); } }
  async function openPortal() { setError(""); try { const value = await api<{ portal_url: string }>("/api/v1/web/billing/portal", { method: "POST", body: JSON.stringify({ return_url: `${window.location.origin}/dashboard/billing` }) }); window.location.assign(value.portal_url); } catch (cause) { setError(cause instanceof Error ? cause.message : "Billing portal could not be opened"); } }
  async function saveOrg(event: FormEvent) { event.preventDefault(); setError(""); try { await api("/api/v1/web/organization", { method: "PATCH", body: JSON.stringify({ name }) }); setResult((current) => ({ ...current, items: current.items.map((item, index) => index === 0 ? { ...item, name } : item) })); } catch (cause) { setError(cause instanceof Error ? cause.message : "Organization could not be updated"); } }

  const emptyCopy = key === "approvals" ? "No requests are waiting for approval." : key === "evidence" ? "No governed activity yet. Connect your first agent and WhitePact will begin evaluating runtime actions." : "No records are available.";
  return <main className="dashboard-content"><div className="page-heading"><div><h1>{config.title}</h1><p>{config.copy}</p></div>{key === "billing" && <span>{session.organization?.plan ?? "FREE"} plan</span>}</div>{error && <div className="form-error" role="alert">{error}</div>}
    {key === "security" ? <section className="security-cards">{[["Browser session", "HttpOnly session cookie, CSRF validation and bounded expiration."], ["API key storage", "Raw secrets are disclosed once; only one-way verifiers remain."], ["Tenant enforcement", "Organization scope is validated on backend reads and mutations."], ["Assurance boundary", "SOC 2 and ISO 27001 certification are not currently claimed."]].map(([title,copy])=><article key={title}><ShieldCheck /><h2>{title}</h2><p>{copy}</p></article>)}</section> : key === "billing" ? <BillingPanel item={result.items[0]} configured={Boolean(result.billing_configured)} onCheckout={startBilling} onPortal={openPortal} /> : key === "organization" && result.items[0] ? <section className="data-panel settings-panel"><form onSubmit={saveOrg}><label className="field"><span>Organization name</span><input value={name} onChange={(event)=>setName(event.target.value)} required minLength={2} /></label><div className="metadata-grid"><p><span>Organization ID</span><code>{String(result.items[0].id)}</code></p><p><span>Slug</span><strong>{String(result.items[0].slug)}</strong></p><p><span>Owner</span><strong>{session.user.full_name}</strong></p><p><span>Plan</span><strong>{String(result.items[0].plan)}</strong></p></div><Button>Save organization</Button></form></section> : result.items.length ? <RecordTable records={result.items} domain={key} /> : <section className="data-panel"><div className="empty-state"><Icon /><h2>No {config.title.toLowerCase()} yet</h2><p>{emptyCopy}</p>{key === "evidence" && <Link to="/dashboard/api-keys">Create an API key <ArrowRight /></Link>}</div></section>}
  </main>;
}

function RecordTable({ records, domain }: { records: DomainRecord[]; domain: string }) { const fields = domain === "members" ? ["full_name","email","role","joined_at"] : domain === "approvals" ? ["approval_id","action_type","risk_tier","status","requested_at"] : ["evidence_id","agent_id","action_type","risk_tier","decision","recorded_at"]; return <section className="data-panel"><div className="record-table" role="table" aria-label={`${domain} records`}><div role="row" className="record-row record-head">{fields.map(field=><span role="columnheader" key={field}>{field.replaceAll("_", " ")}</span>)}</div>{records.map((record,index)=><div role="row" className="record-row" key={String(record.id ?? record.approval_id ?? record.evidence_id ?? index)}>{fields.map(field=><span role="cell" key={field}>{format(record[field])}</span>)}</div>)}</div></section>; }
function format(value: RecordValue | undefined) { if (Array.isArray(value)) return value.join(", "); if (value === null || value === undefined || value === "") return "—"; return String(value); }
function BillingPanel({ item, configured, onCheckout, onPortal }: { item?: DomainRecord; configured: boolean; onCheckout: (plan: "PRO"|"ENTERPRISE")=>void; onPortal: ()=>void }) { const plan=String(item?.plan ?? "FREE"), status=String(item?.subscription_status ?? "inactive"), customer=Boolean(item?.stripe_customer_id); return <section className="billing-panel"><article><span>Current plan</span><strong>{plan}</strong><p>Subscription status: {status}</p>{item?.plan_renews_at && <p>Renews or changes: {String(item.plan_renews_at)}</p>}</article><article><span>Billing connection</span><strong>{configured ? "Available" : "Not configured"}</strong><p>Access changes only after a signed Stripe webhook is processed.</p></article><div className="billing-actions">{plan !== "PRO" && <Button onClick={()=>onCheckout("PRO")} disabled={!configured}>Choose Pro</Button>}{plan !== "ENTERPRISE" && <Button onClick={()=>onCheckout("ENTERPRISE")} disabled={!configured}>Choose Enterprise</Button>}{customer && <Button variant="secondary" onClick={onPortal}>Manage, downgrade or cancel</Button>}</div>{!configured && <p className="configuration-note">Billing is not configured on this deployment. No paid entitlement is being advertised as active.</p>}</section>; }
