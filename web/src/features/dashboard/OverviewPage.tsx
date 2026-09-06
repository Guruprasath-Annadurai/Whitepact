// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { useEffect, useState } from "react";
import { ArrowRight, Bot, FileCheck2, ShieldAlert } from "lucide-react";
import { Link, useOutletContext } from "react-router-dom";
import { api } from "../../lib/api";
import type { WebSession } from "./DashboardShell";

type Summary = { decisions: number; agents: number; pending_approvals: number; blocked_actions: number; recent_governance: Array<{ id: string; agent: string; action: string; policy: string; risk: string; decision: string; timestamp: string }>; services: Record<string, string> };

export function OverviewPage() {
  const session = useOutletContext<WebSession>();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<Summary>("/api/v1/web/dashboard/summary").then(setSummary).catch((cause) => setError(cause instanceof Error ? cause.message : "Governance summary is unavailable")); }, []);
  const name = session.user.full_name.split(" ")[0];
  return <main className="dashboard-content"><div className="page-heading"><div><h1>Good {new Date().getHours() < 12 ? "morning" : new Date().getHours() < 18 ? "afternoon" : "evening"}, {name}</h1><p>{session.organization?.name ?? "Complete onboarding to create your workspace"}</p></div><span>Organization workspace</span></div>{error && <div className="form-error" role="alert">{error}</div>}<section className="summary-rail" aria-label="Persisted governance summary">{[["Governance decisions", summary?.decisions], ["Agents", summary?.agents], ["Pending approvals", summary?.pending_approvals], ["Blocked actions", summary?.blocked_actions]].map(([label, value]) => <div key={label}><span>{label}</span><strong>{value ?? "—"}</strong></div>)}</section><div className="overview-grid"><section className="data-panel governance-panel"><header><div><h2>Recent governance</h2><p>Decisions produced by governed requests in this organization.</p></div><Link to="/dashboard/evidence">View evidence <ArrowRight /></Link></header>{summary?.recent_governance.length ? <div className="data-table" role="table" aria-label="Recent governance decisions"><div className="data-row data-head" role="row">{["Time","Agent","Action","Policy","Risk","Decision"].map(item=><span role="columnheader" key={item}>{item}</span>)}</div>{summary.recent_governance.map((event) => <div className="data-row" role="row" key={event.id}><span role="cell">{event.timestamp}</span><span role="cell">{event.agent}</span><span role="cell">{event.action}</span><span role="cell">{event.policy}</span><span role="cell">{event.risk}</span><span role="cell" className={`decision decision--${event.decision.toLowerCase().replaceAll("_", "-")}`}>{event.decision}</span></div>)}</div> : <div className="empty-state"><FileCheck2 /><h3>No governed activity yet</h3><p>Connect your first agent and WhitePact will begin evaluating runtime actions.</p><Link to="/dashboard/api-keys">Create an API key <ArrowRight /></Link></div>}</section><aside className="data-panel status-panel"><h2>Configured services</h2>{Object.keys(summary?.services ?? {}).length ? Object.entries(summary!.services).map(([service, status]) => <div key={service}><i className={status === "configured" ? "healthy" : "warning"} /><span>{service}</span><strong>{status}</strong></div>) : <><div><Bot /><span>MCP Gateway</span><strong>Unavailable</strong></div><div><ShieldAlert /><span>Policy engine</span><strong>Unavailable</strong></div></>}</aside></div></main>;
}
