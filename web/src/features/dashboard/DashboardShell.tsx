// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { useEffect, useState } from "react";
import { Bell, Bot, Building2, CreditCard, FileCheck2, Gauge, HelpCircle, KeyRound, Menu, Network, Search, Settings, ShieldCheck, Users, X } from "lucide-react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Brand } from "../../components/Brand";
import { api } from "../../lib/api";
import { publicAsset } from "../../lib/assets";

export type WebSession = { user: { full_name: string; email: string }; organization: { id: string; name: string; plan: string } | null };
const primary = [[Gauge, "Overview", "/dashboard"], [Bot, "Agents", "/dashboard/agents"], [KeyRound, "API Keys", "/dashboard/api-keys"], [Network, "Usage", "/dashboard/usage"], [ShieldCheck, "Policies", "/dashboard/policies"], [Users, "Approvals", "/dashboard/approvals"], [FileCheck2, "Evidence", "/dashboard/evidence"], [Network, "MCP Gateway", "/dashboard/mcp"]] as const;
const account = [[Building2, "Organization", "/dashboard/organization"], [Users, "Members", "/dashboard/members"], [CreditCard, "Billing", "/dashboard/billing"], [Settings, "Settings", "/dashboard/settings"]] as const;

export function DashboardShell() {
  const [session, setSession] = useState<WebSession | null>(null);
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  useEffect(() => { api<WebSession>("/api/v1/web/session").then(setSession).catch(() => navigate(`/login?next=${encodeURIComponent(location.pathname)}`)); }, [location.pathname, navigate]);
  async function logout() { await api("/api/v1/web/auth/logout", { method: "POST" }); navigate("/"); }
  if (!session) return <div className="app-loading"><img src={publicAsset("whitepact-mark.png")} alt="" /><span>Verifying session</span></div>;
  return <div className="dashboard-layout"><aside className={open ? "dashboard-sidebar is-open" : "dashboard-sidebar"}><div className="sidebar-head"><Brand compact /><button onClick={() => setOpen(false)} aria-label="Close navigation"><X /></button></div><nav aria-label="Dashboard">{primary.map(([Icon, label, href]) => <NavLink end={href === "/dashboard"} key={href} to={href} onClick={() => setOpen(false)}><Icon />{label}</NavLink>)}<hr />{account.map(([Icon, label, href]) => <NavLink key={href} to={href} onClick={() => setOpen(false)}><Icon />{label}</NavLink>)}</nav><div className="sidebar-account"><strong>{session.organization?.name ?? "No organization"}</strong><small>{session.organization?.plan ?? "Onboarding required"}</small><button onClick={logout}>Sign out</button><span>{session.user.full_name}<small>{session.user.email}</small></span></div></aside><div className="dashboard-main"><header className="dashboard-topbar"><button className="mobile-menu" onClick={() => setOpen(true)} aria-label="Open navigation"><Menu /></button><span className="environment"><i />Production</span><button className="command"><Search /> Search or run a command… <kbd>⌘ K</kbd></button><button aria-label="Notifications"><Bell /></button><a href="/docs" aria-label="Help"><HelpCircle /></a></header><Outlet context={session} /></div></div>;
}
