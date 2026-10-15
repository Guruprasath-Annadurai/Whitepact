// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { useEffect, useRef, useState } from "react";
import { Bot, Building2, CreditCard, FileCheck2, Gauge, HelpCircle, KeyRound, Menu, ScrollText, ShieldCheck, Users, X } from "lucide-react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Brand } from "../../components/Brand";
import { Button } from "../../components/Button";
import { api, ApiError } from "../../lib/api";
import { publicAsset } from "../../lib/assets";

export type WebSession = { user: { full_name: string; email: string }; organization: { id: string; name: string; plan: string; role?: string } | null; organizations?: Array<{ id: string; name: string; role: string }> };
const primary = [[Gauge, "Overview", "/dashboard"], [Bot, "Agents", "/dashboard/agents"], [KeyRound, "API Keys", "/dashboard/api-keys"], [ScrollText, "Policy", "/dashboard/policy"], [Users, "Approvals", "/dashboard/approvals"], [FileCheck2, "Evidence", "/dashboard/evidence"], [ShieldCheck, "Security", "/dashboard/security"]] as const;
const account = [[Building2, "Organization", "/dashboard/organization"], [Users, "Members", "/dashboard/members"], [CreditCard, "Billing", "/dashboard/billing"]] as const;

function validSession(value: unknown): value is WebSession {
  if (!value || typeof value !== "object") return false;
  const candidate = value as WebSession;
  if (!candidate.user || typeof candidate.user.full_name !== "string" || typeof candidate.user.email !== "string") return false;
  return candidate.organization === null || (!!candidate.organization && typeof candidate.organization.id === "string" && typeof candidate.organization.name === "string" && typeof candidate.organization.plan === "string");
}

export function DashboardShell() {
  const [verification, setVerification] = useState<{ path: string; session: WebSession | null; error: "forbidden" | "unavailable" | null }>({ path: "", session: null, error: null });
  const [retry, setRetry] = useState(0);
  const [open, setOpen] = useState(false);
  const [mobile, setMobile] = useState(() => window.matchMedia?.("(max-width: 820px)").matches ?? false);
  const [logoutState, setLogoutState] = useState<"idle" | "busy" | "uncertain">("idle");
  const navigate = useNavigate();
  const location = useLocation();
  const sidebar = useRef<HTMLElement>(null);
  const menuButton = useRef<HTMLButtonElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const session = verification.path === location.pathname ? verification.session : null;
  useEffect(() => {
    const query = window.matchMedia?.("(max-width: 820px)");
    if (!query) return;
    const update = () => { setMobile(query.matches); if (!query.matches) setOpen(false); };
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    api<unknown>("/api/v1/web/session", { signal: controller.signal })
      .then((value) => {
        if (!active) return;
        if (!validSession(value)) throw new Error("Malformed session acknowledgement");
        setVerification({ path: location.pathname, session: value, error: null });
        if (!value.organization && !location.pathname.startsWith("/onboarding")) {
          navigate("/onboarding", { replace: true });
        }
      })
      .catch((cause: unknown) => {
        if (!active) return;
        if (cause instanceof ApiError && cause.status === 401) navigate(`/login?next=${encodeURIComponent(location.pathname)}&reason=session-expired`, { replace: true });
        else setVerification({ path: location.pathname, session: null, error: cause instanceof ApiError && cause.status === 403 ? "forbidden" : "unavailable" });
      });
    return () => { active = false; controller.abort(); };
  }, [location.pathname, navigate, retry]);
  useEffect(() => {
    if (!open) return;
    const node = sidebar.current;
    const restoreTarget = menuButton.current;
    node?.querySelector<HTMLElement>("button,a")?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setOpen(false); return; }
      if (event.key !== "Tab" || !node) return;
      const controls = Array.from(node.querySelectorAll<HTMLElement>("button:not([disabled]),a[href]"));
      if (!controls.length) return;
      const first = controls[0], last = controls.at(-1)!;
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", handler);
    return () => { document.removeEventListener("keydown", handler); restoreTarget?.focus(); };
  }, [open]);
  async function logout() {
    if (logoutState !== "idle") return;
    setLogoutState("busy");
    try {
      const result = await api<{ status?: string }>("/api/v1/web/auth/logout", { method: "POST" });
      if (result?.status !== "signed_out") throw new Error("Unconfirmed sign out");
      navigate("/", { replace: true });
    } catch { setOpen(false); setLogoutState("uncertain"); }
  }
  if (logoutState === "uncertain") return <main className="dashboard-content"><section className="data-panel console-state" role="alert"><h1>Sign out could not be confirmed</h1><p>The request may have completed, but its acknowledgement was unavailable. Workspace data is hidden. Reload to verify the current session before trying again.</p><Button onClick={() => window.location.reload()}>Reload session</Button><a href="/login">Open sign in</a></section></main>;
  if (verification.path === location.pathname && verification.error) return <main className="dashboard-content"><section className="data-panel console-state" role="alert"><h1>{verification.error === "forbidden" ? "Workspace access unavailable" : "Session verification unavailable"}</h1><p>{verification.error === "forbidden" ? "The server did not permit access to this workspace. No authenticated workspace data is shown." : "WhitePact could not verify the session. This does not confirm that the session expired. No authenticated workspace data is shown."}</p><Button onClick={() => { setVerification({ path: "", session: null, error: null }); setRetry((current) => current + 1); }}>Retry session verification</Button><a href="/login">Open sign in</a></section></main>;
  if (!session) return <div className="app-loading" role="status" aria-live="polite"><img src={publicAsset("whitepact-mark.png")} alt="" /><span>Verifying session</span></div>;
  return <div className="dashboard-layout">
    <a className="corporate-skip" inert={mobile && open} href="#workspace-content" onClick={() => content.current?.focus()}>Skip to workspace content</a>
    <aside id="workspace-navigation" ref={sidebar} className={open ? "dashboard-sidebar is-open" : "dashboard-sidebar"} aria-label="Workspace navigation" role={mobile && open ? "dialog" : undefined} aria-modal={mobile && open ? true : undefined} inert={mobile && !open} aria-hidden={mobile && !open ? true : undefined}>
      <div className="sidebar-head"><Brand compact /><button onClick={() => setOpen(false)} aria-label="Close navigation"><X aria-hidden="true" /></button></div>
      <nav aria-label="Dashboard">{primary.map(([Icon, label, href]) => <NavLink end={href === "/dashboard"} key={href} to={href} onClick={() => setOpen(false)}><Icon aria-hidden="true" />{label}</NavLink>)}<hr />{account.map(([Icon, label, href]) => <NavLink key={href} to={href} onClick={() => setOpen(false)}><Icon aria-hidden="true" />{label}</NavLink>)}</nav>
      <div className="sidebar-account"><strong>{session.organization?.name ?? "No organization"}</strong><small>{session.organization?.plan ?? "Onboarding required"}</small><button disabled={logoutState === "busy"} onClick={() => void logout()}>{logoutState === "busy" ? "Signing out…" : "Sign out"}</button><span>{session.user.full_name}<small>{session.user.email}</small></span></div>
    </aside>
    {open && <button className="sidebar-scrim" aria-label="Close navigation" tabIndex={-1} onClick={() => setOpen(false)} />}
    <div className="dashboard-main" inert={mobile && open}>
      <header className="dashboard-topbar"><button ref={menuButton} className="mobile-menu" onClick={() => setOpen(true)} aria-label="Open navigation" aria-expanded={open} aria-controls="workspace-navigation"><Menu aria-hidden="true" /></button><span className="environment"><i />Workspace</span><a href="/docs" aria-label="Open documentation"><HelpCircle aria-hidden="true" /></a></header>
      <div id="workspace-content" ref={content} tabIndex={-1}><Outlet context={session} /></div>
    </div>
  </div>;
}
