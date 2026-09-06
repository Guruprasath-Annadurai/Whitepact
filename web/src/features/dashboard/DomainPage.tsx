// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { useEffect, useState } from "react";
import { ArrowRight, CreditCard, FileCheck2, Network, ShieldCheck, Users } from "lucide-react";
import { Link, useOutletContext, useParams } from "react-router-dom";
import { api } from "../../lib/api";
import type { WebSession } from "./DashboardShell";

const domains: Record<string, { title: string; copy: string; empty: string; action: string; href: string; icon: typeof Users }> = {
  agents: { title: "Agents", copy: "Identity, authority and runtime status across your agent estate.", empty: "Connect your first agent to start governing runtime actions.", action: "Create an API key", href: "/dashboard/api-keys", icon: Users },
  usage: { title: "Usage", copy: "Governance-unit consumption for the current billing period.", empty: "Usage appears after your first governed request.", action: "View integration guide", href: "/docs", icon: Network },
  policies: { title: "Policies", copy: "Human-readable rules evaluated at the action boundary.", empty: "No organization policies have been created.", action: "Read policy documentation", href: "/docs", icon: ShieldCheck },
  approvals: { title: "Approvals", copy: "Requests waiting for an authorized human decision.", empty: "No requests are waiting for approval.", action: "Review approval documentation", href: "/docs", icon: Users },
  evidence: { title: "Evidence", copy: "Hash-chained decision records and verification results.", empty: "Evidence appears after the first governance decision.", action: "Learn about integrity", href: "/trust", icon: FileCheck2 },
  mcp: { title: "MCP Gateway", copy: "Connection state and recent governed tool calls.", empty: "No MCP clients are connected to this organization.", action: "View MCP setup", href: "/docs", icon: Network },
  organization: { title: "Organization", copy: "Workspace identity and production configuration.", empty: "Your organization is active. Additional organization settings appear when configured.", action: "Review API keys", href: "/dashboard/api-keys", icon: Users },
  members: { title: "Members", copy: "People and enforced roles in this organization.", empty: "No additional members have been invited. Invitations are disabled until an identity provider is configured.", action: "Review security", href: "/trust", icon: Users },
  billing: { title: "Billing", copy: "Subscription, entitlement, usage and invoices.", empty: "No paid subscription is active. Access is never unlocked from a redirect alone.", action: "Choose plan", href: "/dashboard/billing", icon: CreditCard },
  settings: { title: "Settings", copy: "Account, security, notifications, integrations and retention.", empty: "Security-sensitive settings are controlled by deployment policy.", action: "Review security", href: "/trust", icon: ShieldCheck },
};

export function DomainPage() {
  const { domain = "" } = useParams();
  const config = domains[domain] ?? domains.agents;
  const [items, setItems] = useState<unknown[]>([]);
  const [error, setError] = useState("");
  const session = useOutletContext<WebSession>();
  const Icon = config.icon;

  useEffect(() => { api<{ items?: unknown[] }>(`/api/v1/web/dashboard/${domain}`).then((result) => setItems(result.items ?? [])).catch(() => setItems([])); }, [domain]);

  async function startBilling(plan: "PRO" | "ENTERPRISE") {
    setError("");
    try {
      const result = await api<{ checkout_url: string }>("/api/v1/web/billing/checkout", { method: "POST", body: JSON.stringify({ plan }) });
      window.location.assign(result.checkout_url);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Billing could not be started"); }
  }

  const billing = domain === "billing";
  return <main className="dashboard-content"><div className="page-heading"><div><h1>{config.title}</h1><p>{config.copy}</p></div>{billing && <span>{session.organization?.plan ?? "FREE"} plan</span>}</div><section className="data-panel domain-panel">{items.length ? <pre>{JSON.stringify(items, null, 2)}</pre> : <div className="empty-state"><Icon /><h3>{config.title} is ready</h3><p>{config.empty}</p>{billing ? <div className="billing-actions"><button onClick={() => startBilling("PRO")}>Start Pro checkout <ArrowRight /></button><button onClick={() => startBilling("ENTERPRISE")}>Enterprise checkout <ArrowRight /></button></div> : <Link to={config.href}>{config.action} <ArrowRight /></Link>}{error && <div className="form-error" role="alert">{error}</div>}</div>}</section></main>;
}
