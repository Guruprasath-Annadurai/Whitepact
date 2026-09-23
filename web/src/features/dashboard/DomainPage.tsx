// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AlertTriangle, ArrowRight, Building2, CheckCircle2, CreditCard, FileCheck2, RotateCw, ShieldCheck, Users, X } from "lucide-react";
import { Link, useOutletContext, useParams } from "react-router-dom";
import { AccessibleDialog } from "../../components/AccessibleDialog";
import { Button } from "../../components/Button";
import { ApiError, api, messageFrom } from "../../lib/api";
import { openPaddleTransactionCheckout } from "../../lib/paddleCheckout";
import type { ApprovalExecutionResponse, ApprovalResolution, ConsequentialOutcome, DomainRecord, DomainResponse, EvidenceListResponse, InvitationRecord, LoadState, RecordValue } from "../../lib/contracts";
import type { WebSession } from "./DashboardShell";
import { ApprovalContractPanel, EvidenceContractPanel } from "./CanonicalPanels";

const supported = {
  approvals: { title: "Approvals", copy: "Requests waiting for an authorized human decision.", icon: Users },
  evidence: { title: "Evidence", copy: "Tenant-scoped governance decision records returned by WhitePact.", icon: FileCheck2 },
  organization: { title: "Organization", copy: "Workspace identity, ownership and plan metadata.", icon: Building2 },
  members: { title: "Members", copy: "Verified people, roles and pending invitations in this organization.", icon: Users },
  billing: { title: "Billing", copy: "Subscription state and entitlement management. This page is not a usage meter.", icon: CreditCard },
  security: { title: "Security posture", copy: "Read-only security status loaded from backend identity stores.", icon: ShieldCheck },
} as const;

export function DomainPage({ domainKey }: { domainKey?: keyof typeof supported }) {
  const { domain = "" } = useParams();
  const key = domainKey ?? domain as keyof typeof supported;
  const config = supported[key];
  const [result, setResult] = useState<DomainResponse>({ items: [], source: "loading" });
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const session = useOutletContext<WebSession>();

  const load = useCallback(async () => {
    if (!config) return;
    try {
      const value = key === "evidence"
        ? await api<EvidenceListResponse>("/api/v1/web/evidence?limit=50").then((payload) => ({ items: payload.evidence, source: `bounded evidence list (limit ${payload.limit})` }))
        : await api<DomainResponse>(`/api/v1/web/dashboard/${key}`);
      setResult(value); setError("");
      if (key === "organization") setName(String(value.items[0]?.name ?? ""));
      setState(value.items.length ? "success" : "empty");
    } catch (cause) { setError(messageFrom(cause, "Could not load this section")); setState("error"); }
  }, [config, key]);
  useEffect(() => { const task = window.setTimeout(() => void load(), 0); return () => window.clearTimeout(task); }, [load]);
  if (!config) return null;
  const Icon = config.icon;

  async function saveOrg(event: FormEvent) {
    event.preventDefault(); setError("");
    try { await api("/api/v1/web/organization", { method: "PATCH", body: JSON.stringify({ name }) }); setResult((current) => ({ ...current, items: current.items.map((item, index) => index === 0 ? { ...item, name } : item) })); }
    catch (cause) { setError(messageFrom(cause, "Organization could not be updated")); }
  }

  return <main className="dashboard-content"><div className="page-heading"><div><h1>{config.title}</h1><p>{config.copy}</p></div>{key === "billing" && <span>{session.organization?.plan ?? "FREE"} plan</span>}</div>{error && <div className="form-error" role="alert" aria-live="assertive">{error}</div>}
    {state === "loading" ? <LoadingState /> : state === "error" ? <ErrorState onRetry={load} /> : key === "security" ? <SecurityCards items={result.items} source={result.source} /> : key === "billing" ? <BillingPanel item={result.items[0]} configured={Boolean(result.billing_configured)} onError={setError} /> : key === "organization" && result.items[0] ? <section className="data-panel settings-panel"><form onSubmit={saveOrg}><label className="field"><span>Organization name</span><input value={name} onChange={(event)=>setName(event.target.value)} required minLength={2} /></label><div className="metadata-grid"><p><span>Organization ID</span><code>{String(result.items[0].id)}</code></p><p><span>Slug</span><strong>{String(result.items[0].slug)}</strong></p><p><span>Owner</span><strong>{session.user.full_name}</strong></p><p><span>Plan</span><strong>{String(result.items[0].plan)}</strong></p></div><Button>Save organization</Button></form></section> : key === "members" ? <MembersPanel records={result.items} session={session} onError={setError} onChanged={load} /> : key === "approvals" ? <ApprovalContractPanel records={result.items} onError={setError} onChanged={load} /> : key === "evidence" ? <EvidenceContractPanel records={result.items} /> : <EmptyState icon={Icon} title={config.title} keyName={key} />}
  </main>;
}

function LoadingState() { return <section className="data-panel console-state" role="status" aria-live="polite"><RotateCw className="spin" aria-hidden="true" /><h2>Loading current state…</h2></section>; }
function ErrorState({ onRetry }: { onRetry: () => Promise<void> }) { return <section className="data-panel console-state"><AlertTriangle aria-hidden="true" /><h2>This section could not be loaded</h2><p>The request failed; WhitePact has not presented it as an empty dataset.</p><Button variant="secondary" onClick={() => void onRetry()}>Retry</Button></section>; }
function EmptyState({ icon: Icon, title, keyName }: { icon: typeof Users; title: string; keyName: string }) { return <section className="data-panel"><div className="empty-state"><Icon aria-hidden="true" /><h2>No {title.toLowerCase()} yet</h2><p>{keyName === "evidence" ? "No governed activity has been returned for this organization." : keyName === "approvals" ? "No requests are waiting for approval." : "No records are available."}</p>{keyName === "evidence" && <Link to="/dashboard/api-keys">Create an API key <ArrowRight /></Link>}</div></section>; }

function SecurityCards({ items, source }: { items: DomainRecord[]; source: string }) {
  if (!items.length) return <section className="security-cards"><article><ShieldCheck aria-hidden="true" /><h2>Security state</h2><strong className="posture posture--unavailable">Unavailable</strong><p>Backend security state has not been returned.</p><small>source: {source}</small></article></section>;
  return <><p className="configuration-note">This V1 page reports security posture. MFA, passkey and recovery-factor management are not available in the V1 console.</p><section className="security-cards">{items.map((item) => { const status=String(item.status ?? "UNAVAILABLE"); const tone=status.includes("NOT CONFIGURED") ? "missing" : status.includes("UNAVAILABLE") ? "unavailable" : "configured"; return <article key={String(item.title)}><ShieldCheck aria-hidden="true" /><h2>{format(item.title)}</h2><strong className={`posture posture--${tone}`}>{format(status)}</strong><p>{format(item.detail)}</p><small>source: {format(item.source)}</small></article>; })}</section></>;
}

type PendingDecision = { record: DomainRecord; outcome: "APPROVED" | "DENIED" };
export function ApprovalsPanel({ records, onError, onChanged }: { records: DomainRecord[]; onError: (value: string) => void; onChanged: () => Promise<void> }) {
  const [busy, setBusy] = useState(false); const [confirm, setConfirm] = useState<PendingDecision | null>(null); const [outcome, setOutcome] = useState<ConsequentialOutcome | null>(null); const closeConfirm = useCallback(() => setConfirm(null), []);
  async function decide() {
    if (!confirm) return;
    const id=String(confirm.record.approval_id ?? ""), requested=confirm.outcome; setBusy(true); onError(""); setOutcome(null);
    try {
      const resolved=await api<ApprovalResolution>(`/api/v1/web/approvals/${id}/resolve`,{method:"POST",body:JSON.stringify({outcome:requested})});
      if (requested === "DENIED") { setOutcome({state:"DENIED",approvalId:id}); setConfirm(null); await onChanged(); return; }
      if (resolved.status !== "APPROVED") { const required=Number(resolved.required_approvals ?? confirm.record.required_approvals ?? 2); setOutcome({state:"PENDING",approvalId:id,recorded:1,required}); setConfirm(null); await onChanged(); return; }
      const executed=await api<ApprovalExecutionResponse>(`/api/v1/web/approvals/${id}/execute`,{method:"POST",body:JSON.stringify({})});
      if (executed.execution_status === "UNKNOWN") { setOutcome({state:"UNKNOWN",approvalId:id,message:executed.message || "WhitePact cannot currently confirm whether the downstream effect occurred.",reconciliationRequired:executed.reconciliation_required,evidenceId:executed.evidence_id??undefined,outcomeId:executed.outcome_id??undefined}); setConfirm(null); return; }
      setOutcome({state:"SUCCESS",approvalId:id,message:executed.message,evidenceId:executed.evidence_id??undefined,outcomeId:executed.outcome_id??undefined}); setConfirm(null); await onChanged();
    } catch (cause) { const message=messageFrom(cause,"Approval could not be submitted"); setOutcome({state:"FAILED",approvalId:id,message}); setConfirm(null); }
    finally { setBusy(false); }
  }
  if (!records.length && !outcome) return <EmptyState icon={Users} title="approvals" keyName="approvals" />;
  return <>{outcome && <OutcomeNotice outcome={outcome} />}<section className="data-panel approval-list">{records.map((record) => { const id=String(record.approval_id ?? ""), status=String(record.status ?? "PENDING"), required=Number(record.required_approvals ?? 1); return <article key={id} className="approval-card"><header><h2>{format(record.action_type)}</h2><span>{status}</span></header><dl><div><dt>Approval ID</dt><dd>{id}</dd></div><div><dt>Target</dt><dd>{format(record.target)}</dd></div><div><dt>Risk</dt><dd>{format(record.risk_tier)}</dd></div><div><dt>Approval requirement</dt><dd>{required > 1 ? `${required} distinct authorized approvers` : "1 authorized approver"}</dd></div><div><dt>Requested</dt><dd>{format(record.requested_at)}</dd></div><div><dt>Requested by</dt><dd>{format(record.requested_by)}</dd></div></dl><div className="approval-actions"><Button disabled={busy || status !== "PENDING"} onClick={()=>setConfirm({record,outcome:"APPROVED"})}>Approve</Button><Button variant="danger" disabled={busy || status !== "PENDING"} onClick={()=>setConfirm({record,outcome:"DENIED"})}>Deny</Button></div></article>; })}</section>{confirm && <AccessibleDialog labelId="approval-confirm-title" onClose={closeConfirm}><header><div><h2 id="approval-confirm-title">{confirm.outcome === "APPROVED" ? "Approve" : "Deny"} this request?</h2><p>{format(confirm.record.action_type)} → {format(confirm.record.target)}</p></div><button onClick={closeConfirm} aria-label="Close"><X /></button></header><p>This records your decision through the backend approval path. It does not create authority in the browser.</p><div className="modal-actions"><Button variant={confirm.outcome === "DENIED" ? "danger" : "primary"} disabled={busy} onClick={()=>void decide()}>{busy ? "Submitting…" : `Confirm ${confirm.outcome.toLowerCase()}`}</Button><Button variant="secondary" disabled={busy} onClick={closeConfirm}>Cancel</Button></div></AccessibleDialog>}</>;
}

function OutcomeNotice({ outcome }: { outcome: ConsequentialOutcome }) {
  if (outcome.state === "UNKNOWN") return <section className="outcome-notice outcome-notice--unknown" role="alert" aria-live="assertive"><AlertTriangle aria-hidden="true" /><div><h2>Execution outcome is uncertain</h2><p>{outcome.message}</p><p>Do not retry automatically. Inspect the evidence before taking any further action.</p>{outcome.evidenceId && <Link to="/dashboard/evidence">Inspect evidence {outcome.evidenceId}</Link>}</div></section>;
  if (outcome.state === "PENDING") return <section className="outcome-notice" role="status" aria-live="polite"><Users aria-hidden="true" /><div><h2>{outcome.recorded} of {outcome.required} approvals recorded</h2><p>Waiting for another authorized approver. No execution has been started.</p></div></section>;
  if (outcome.state === "SUCCESS") return <section className="outcome-notice outcome-notice--success" role="status"><CheckCircle2 aria-hidden="true" /><div><h2>Approval resolved and execution acknowledged</h2></div></section>;
  if (outcome.state === "DENIED") return <section className="outcome-notice" role="status"><ShieldCheck aria-hidden="true" /><div><h2>Request denied</h2><p>No execution was requested by this action.</p></div></section>;
  return <section className="outcome-notice outcome-notice--error" role="alert"><AlertTriangle aria-hidden="true" /><div><h2>Request could not be completed</h2><p>{outcome.message}</p></div></section>;
}

export function EvidencePanel({ records }: { records: DomainRecord[] }) {
  const [query,setQuery]=useState(""); const [selected,setSelected]=useState<DomainRecord|null>(null); const close=useCallback(()=>setSelected(null),[]);
  const filtered=records.filter((record)=>[record.evidence_id,record.agent_id,record.identity_id,record.action_type,record.target,record.decision].some((value)=>String(value??"").toLowerCase().includes(query.toLowerCase())));
  if (!records.length) return <EmptyState icon={FileCheck2} title="evidence" keyName="evidence" />;
  return <><section className="data-panel evidence-ledger"><header><div><h2>Loaded evidence records</h2><p>Filter applies only to the {records.length} records loaded on this page; it is not server pagination.</p></div><label className="field compact-field"><span>Filter loaded records</span><input type="search" value={query} onChange={(e)=>setQuery(e.target.value)} /></label></header><div className="evidence-cards">{filtered.map((record,index)=><article key={String(record.evidence_id??index)}><div><span className={`decision decision--${String(record.decision??"").toLowerCase().replaceAll("_","-")}`}>{format(record.decision)}</span><time>{format(record.recorded_at ?? record.evaluated_at)}</time></div><h2>{format(record.action_type)}</h2><dl><div><dt>Actor</dt><dd>{format(record.agent_id ?? record.identity_id)}</dd></div><div><dt>Target</dt><dd>{format(record.target ?? record.execution_target)}</dd></div><div><dt>Evidence ID</dt><dd><code>{format(record.evidence_id)}</code></dd></div><div><dt>Integrity</dt><dd>{format(record.integrity_status)}</dd></div></dl><Button variant="secondary" onClick={()=>setSelected(record)}>View details</Button></article>)}</div>{!filtered.length&&<div className="empty-state"><FileCheck2/><h3>No loaded records match</h3></div>}</section>{selected&&<AccessibleDialog labelId="evidence-detail-title" onClose={close} className="evidence-detail"><header><div><h2 id="evidence-detail-title">Evidence details</h2><p>{format(selected.evidence_id)}</p></div><button onClick={close} aria-label="Close"><X /></button></header><dl>{Object.entries(selected).filter(([,v])=>v!==null&&v!=="").map(([key,value])=><div key={key}><dt>{key.replaceAll("_"," ")}</dt><dd>{format(value)}</dd></div>)}</dl><p className="configuration-note">This view reports the record returned by the current API. It does not claim chain verification or reconciliation.</p></AccessibleDialog>}</>;
}

function MembersPanel({ records, session, onError, onChanged }: { records: DomainRecord[]; session: WebSession; onError:(v:string)=>void; onChanged:()=>Promise<void> }) {
  const [email,setEmail]=useState(""); const [role,setRole]=useState("VIEWER"); const [busy,setBusy]=useState(""); const [invitations,setInvitations]=useState<InvitationRecord[]>([]); const [confirm,setConfirm]=useState<{kind:"invitation"|"member";id:string;label:string}|null>(null); const close=useCallback(()=>setConfirm(null),[]);
  const canManage=["OWNER","ADMIN"].includes(session.organization?.role??"");
  const loadInvitations=useCallback(async()=>{ if(!canManage)return; try{const value=await api<{invitations:InvitationRecord[]}>("/api/v1/web/invitations");setInvitations(value.invitations);}catch(cause){onError(messageFrom(cause,"Pending invitations could not be loaded"));}},[canManage,onError]);
  useEffect(()=>{void loadInvitations();},[loadInvitations]);
  async function invite(event:FormEvent){event.preventDefault();setBusy("invite");onError("");try{await api("/api/v1/web/invitations",{method:"POST",body:JSON.stringify({email,role})});setEmail("");await loadInvitations();}catch(cause){onError(messageFrom(cause,"Invitation could not be sent"));}finally{setBusy("");}}
  async function updateMember(id:string,nextRole:string){setBusy(id);onError("");try{await api(`/api/v1/web/members/${id}`,{method:"PATCH",body:JSON.stringify({role:nextRole})});await onChanged();}catch(cause){onError(messageFrom(cause,"Member role could not be updated"));}finally{setBusy("");}}
  async function removeConfirmed(){if(!confirm)return;setBusy(confirm.id);onError("");try{const url=confirm.kind==="invitation"?`/api/v1/web/invitations/${confirm.id}`:`/api/v1/web/members/${confirm.id}`;await api(url,{method:"DELETE"});if(confirm.kind==="invitation")await loadInvitations();else await onChanged();setConfirm(null);}catch(cause){onError(messageFrom(cause,confirm.kind==="invitation"?"Invitation could not be revoked":"Member could not be removed"));}finally{setBusy("");}}
  return <>{canManage&&<section className="data-panel settings-panel"><form onSubmit={invite}><h2>Invite a member</h2><label className="field"><span>Email</span><input type="email" value={email} onChange={(e)=>setEmail(e.target.value)} required /></label><label className="field"><span>Role</span><select value={role} onChange={(e)=>setRole(e.target.value)}><option value="ADMIN">Admin</option><option value="ANALYST">Analyst</option><option value="VIEWER">Viewer</option></select></label><Button disabled={Boolean(busy)}>{busy==="invite"?"Sending…":"Send invitation"}</Button></form></section>}<section className="data-panel member-cards"><header><h2>Members</h2></header>{records.map((record,index)=>{const id=String(record.user_id??record.id??index),own=String(record.email)===session.user.email,memberRole=String(record.role??"VIEWER");return <article key={id}><div><strong>{format(record.full_name)}</strong><span>{format(record.email)}</span></div><select aria-label={`Role for ${format(record.email)}`} value={memberRole} disabled={!canManage||own||Boolean(busy)} onChange={(e)=>void updateMember(id,e.target.value)}><option value="OWNER">Owner</option><option value="ADMIN">Admin</option><option value="ANALYST">Analyst</option><option value="VIEWER">Viewer</option></select>{canManage&&!own&&<Button variant="danger" disabled={Boolean(busy)} onClick={()=>setConfirm({kind:"member",id,label:String(record.email)})}>Remove</Button>}</article>})}</section>{canManage&&<section className="data-panel member-cards"><header><h2>Pending invitations</h2></header>{invitations.length?invitations.map((item,index)=>{const id=String(item.id??item.invitation_id??index);return <article key={id}><div><strong>{format(item.email)}</strong><span>{format(item.role)} · {format(item.status)}</span></div><Button variant="danger" disabled={Boolean(busy)} onClick={()=>setConfirm({kind:"invitation",id,label:String(item.email)})}>Revoke invitation</Button></article>}):<p className="configuration-note">No pending invitations.</p>}</section>}{confirm&&<AccessibleDialog labelId="member-confirm-title" onClose={close}><header><div><h2 id="member-confirm-title">{confirm.kind==="invitation"?"Revoke invitation?":"Remove member?"}</h2><p>{confirm.label}</p></div><button onClick={close} aria-label="Close"><X/></button></header><p>This is a destructive organization change and may be rejected by backend role or ownership rules.</p><div className="modal-actions"><Button variant="danger" disabled={Boolean(busy)} onClick={()=>void removeConfirmed()}>{busy?"Submitting…":"Confirm"}</Button><Button variant="secondary" disabled={Boolean(busy)} onClick={close}>Cancel</Button></div></AccessibleDialog>}</>;
}

function BillingPanel({ item, configured, onError }: { item?: DomainRecord; configured: boolean; onError: (value: string) => void }) {
  const [busy, setBusy] = useState<"" | "checkout" | "portal">("");
  const plan = String(item?.plan ?? "FREE");
  const status = String(item?.subscription_status ?? "inactive");
  const paddleCustomerId = item?.paddle_customer_id;
  const hasPaddleCustomer = typeof paddleCustomerId === "string" && paddleCustomerId.trim().length > 0;

  async function redirect(kind: "checkout" | "portal", target?: "PRO" | "ENTERPRISE") {
    setBusy(kind);
    onError("");
    try {
      const url = kind === "checkout" ? "/api/v1/web/billing/checkout" : "/api/v1/web/billing/portal";
      const body = kind === "checkout" ? { plan: target } : {};
      const value = await api<{ checkout_url?: string; portal_url?: string }>(url, { method: "POST", body: JSON.stringify(body) });
      if (kind === "checkout") {
        if (!value.checkout_url) throw new Error("Billing provider did not return a checkout destination.");
        await openPaddleTransactionCheckout(value.checkout_url);
        return;
      }
      const destination = value.portal_url;
      if (!destination) throw new Error("Billing provider did not return a destination.");
      window.location.assign(destination);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) {
        onError("Your session has expired. Sign in again to manage billing.");
      } else if (kind === "portal" && cause instanceof ApiError && cause.status === 404) {
        onError("No Paddle customer subscription is available for this organization.");
      } else if (cause instanceof ApiError && cause.status === 503) {
        onError("Billing management is temporarily unavailable. Try again later.");
      } else {
        onError(messageFrom(cause, "Billing action could not be started"));
      }
    } finally {
      setBusy("");
    }
  }

  return <section className="billing-panel">
    <article><span>Current plan</span><strong>{plan}</strong><p>Subscription status: {status}</p></article>
    <article><span>Billing connection</span><strong>{configured ? "Available" : "Not configured"}</strong><p>Access changes only after a signed billing webhook is processed. WhitePact V1 does not expose a customer usage meter.</p></article>
    <div className="billing-actions">
      {plan !== "PRO" && <Button onClick={() => void redirect("checkout", "PRO")} disabled={!configured || Boolean(busy)}>{busy === "checkout" ? "Opening checkout…" : "Choose Pro"}</Button>}
      {plan !== "ENTERPRISE" && <Button onClick={() => void redirect("checkout", "ENTERPRISE")} disabled={!configured || Boolean(busy)}>{busy === "checkout" ? "Opening checkout…" : "Choose Enterprise"}</Button>}
      {hasPaddleCustomer && <Button variant="secondary" onClick={() => void redirect("portal")} disabled={Boolean(busy)}>{busy === "portal" ? "Opening portal…" : "Manage, downgrade or cancel"}</Button>}
    </div>
    {!configured && <p className="configuration-note">Billing is not configured on this deployment. No paid entitlement is being advertised as active.</p>}
    {configured && !hasPaddleCustomer && <p className="configuration-note">Subscription management becomes available after a Paddle customer subscription is linked to this organization.</p>}
  </section>;
}
function format(value:RecordValue|undefined){if(Array.isArray(value))return value.join(", ");if(value===null||value===undefined||value==="")return "—";return String(value);}
