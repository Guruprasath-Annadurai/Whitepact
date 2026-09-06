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
  useEffect(() => { api<Summary>("/api/v1/web/dashboard/summary").then(setSummary).catch(() => setSummary({ decisions: 0, agents: 0, pending_approvals: 0, blocked_actions: 0, recent_governance: [], services: {} })); }, []);
  const name = session.user.full_name.split(" ")[0];
  return <main className="dashboard-content"><div className="page-heading"><div><h1>Good {new Date().getHours() < 12 ? "morning" : new Date().getHours() < 18 ? "afternoon" : "evening"}, {name}</h1><p>{session.organization?.name ?? "Complete onboarding to create your workspace"}</p></div><span>Production</span></div><section className="summary-rail">{[["Governance decisions", summary?.decisions ?? 0], ["Agents", summary?.agents ?? 0], ["Pending approvals", summary?.pending_approvals ?? 0], ["Blocked actions", summary?.blocked_actions ?? 0]].map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</section><div className="overview-grid"><section className="data-panel governance-panel"><header><div><h2>Recent governance</h2><p>Decisions produced by governed requests in this organization.</p></div><Link to="/dashboard/evidence">View evidence <ArrowRight /></Link></header>{summary?.recent_governance.length ? <div className="data-table" role="table"><div className="data-row data-head" role="row"><span>Time</span><span>Agent</span><span>Action</span><span>Policy</span><span>Risk</span><span>Decision</span></div>{summary.recent_governance.map((event) => <div className="data-row" role="row" key={event.id}><span>{event.timestamp}</span><span>{event.agent}</span><span>{event.action}</span><span>{event.policy}</span><span>{event.risk}</span><span className={`decision decision--${event.decision.toLowerCase().replaceAll("_", "-")}`}>{event.decision}</span></div>)}</div> : <div className="empty-state"><FileCheck2 /><h3>No governance activity</h3><p>Once an agent sends its first governed request, decisions will appear here.</p><Link to="/dashboard/api-keys">Create an API key <ArrowRight /></Link></div>}</section><aside className="data-panel status-panel"><h2>System status</h2>{Object.keys(summary?.services ?? {}).length ? Object.entries(summary!.services).map(([name, status]) => <div key={name}><i className={status === "healthy" ? "healthy" : "warning"} /><span>{name}</span><strong>{status}</strong></div>) : <><div><Bot /><span>MCP Gateway</span><strong>Checking</strong></div><div><ShieldAlert /><span>Policy engine</span><strong>Checking</strong></div></>}</aside></div></main>;
}
