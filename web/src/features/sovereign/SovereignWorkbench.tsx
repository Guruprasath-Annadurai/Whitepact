// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { useEffect, useState } from "react";
import { Binary, Braces, ChevronLeft, CircleHelp, Clock3, Eye, FileCheck2, FlaskConical, GitCompareArrows, ListTree, Menu, Network, PackageCheck, PanelRightClose, Radar, Route, ScanSearch, Search, ShieldCheck, X, ZoomIn, ZoomOut } from "lucide-react";
import { Link } from "react-router-dom";
import type { SovereignCapabilities } from "../../../../sdk/typescript/sovereign/types";
import { Brand } from "../../components/Brand";
import { Seo } from "../../components/Seo";
import { browserCapabilityState, sovereignFixturesAllowed, sovereignWebApi, type SovereignFeatureName } from "./SovereignApi";

const tools = [
  ["Authority Lens", Network, "xray"], ["Expected vs Effective", GitCompareArrows, "authority_compare"], ["Debugger", ScanSearch, "explain"], ["Trace", Route, "trace"], ["Blast Radius", Radar, "simulate_blast_radius"], ["Mission Simulator", Binary, "simulate_mission"], ["Shadow Mode", Eye, "shadow"], ["Policy Lab", FlaskConical, "policy_lab"], ["Gauntlet", ShieldCheck, "gauntlet"], ["Flight Recorder", FileCheck2, "flight_recorder"], ["Time Machine", Clock3, "time_machine"], ["Evidence Explorer", Braces, "evidence"], ["Capsules", PackageCheck, "capsule"], ["Authority BOM", ListTree, "authority_bom"],
] as const;
const nodes = ["Identity", "Authority", "Policy", "Risk", "Approval", "Decision", "Evidence"];

export function SovereignWorkbench() {
  const [active, setActive] = useState("Authority Lens");
  const [selected, setSelected] = useState("Authority");
  const [tab, setTab] = useState("Overview");
  const [notice, setNotice] = useState(true);
  const [sidebar, setSidebar] = useState(false);
  const [capabilities, setCapabilities] = useState<SovereignCapabilities | null>(null);
  const [coreVersion, setCoreVersion] = useState<string | null>(null);
  const [negotiation, setNegotiation] = useState<"loading" | "ready" | "error">("loading");
  const fixtureAllowed = sovereignFixturesAllowed(import.meta.env.DEV);
  const feature = tools.find(([name]) => name === active)?.[2] as SovereignFeatureName;
  const browserState = browserCapabilityState(capabilities, feature);
  const showFixture = fixtureAllowed && active === "Authority Lens";
  const showEvidence = active === "Evidence Explorer";
  useEffect(() => {
    let current = true;
    sovereignWebApi.negotiate().then(({ status, capabilities: negotiated }) => {
      if (!current) return;
      setCapabilities(negotiated);
      setCoreVersion(status.sovereign_version);
      setNegotiation("ready");
    }).catch(() => { if (current) setNegotiation("error"); });
    return () => { current = false; };
  }, []);
  return <div className="sov-workbench"><Seo title="Sovereign Workbench | WhitePact" description="WhitePact Sovereign capability and authority analysis workbench." path="/sovereign/workbench" noIndex />
    <header className="sov-workbench__top"><button className="sov-mobile-toggle" onClick={() => setSidebar(true)} aria-label="Open Sovereign navigation"><Menu /></button><Brand /><span>Sovereign</span><nav><Link to="/dashboard/evidence"><FileCheck2 /> Evidence</Link><Link to="/docs"><CircleHelp /> Help</Link></nav></header>
    <aside aria-label="Sovereign tool navigation" className={sidebar ? "sov-workbench__nav is-open" : "sov-workbench__nav"}><button className="sov-nav-close" onClick={() => setSidebar(false)} aria-label="Close Sovereign navigation"><X /></button><nav aria-label="Sovereign tools">{tools.map(([name, Icon, capability]) => { const state = browserCapabilityState(capabilities, capability); return <button aria-label={name} className={active === name ? "active" : ""} key={name} onClick={() => { setActive(name); setSidebar(false); }}><Icon /><span>{name}</span><small aria-hidden="true">{state === "EXPERIMENTAL" ? "Experimental" : state === "AVAILABLE" ? "Available" : "Unavailable"}</small></button>; })}</nav><Link to="/sovereign"><ChevronLeft /> Product page</Link></aside>
    {sidebar && <button className="sov-workbench__scrim" onClick={() => setSidebar(false)} aria-label="Close Sovereign navigation" />}
    <main className="sov-workbench__main"><header><div><h1>{active}</h1><p>{active === "Authority Lens" ? "Inspect configured authority relationships and supporting evidence." : "Capability state is negotiated from Sovereign Core."}</p></div><div className="mode-switch" aria-label="Data mode"><button aria-pressed={showFixture} disabled={!fixtureAllowed}>Development preview</button><button aria-pressed={!showFixture} disabled={browserState !== "AVAILABLE"}>Production</button><span>{negotiation === "loading" ? "Negotiating" : browserState === "EXPERIMENTAL" ? "Experimental" : browserState === "AVAILABLE" ? "Available" : "Unavailable"}</span></div></header>
      {showFixture && notice && <section className="fixture-notice" role="status"><CircleHelp /><div><strong>Development fixture — not production authority data</strong><p>This environment contains fixture data for UI and integration development. No production authority result is displayed.</p></div><button onClick={() => setNotice(false)}>Dismiss <X /></button></section>}
      {negotiation === "loading" && !showFixture ? <NegotiationState title="Negotiating Sovereign capabilities" copy="Reading canonical status and capability descriptors." /> : negotiation === "error" && !showFixture ? <NegotiationState title="Sovereign negotiation unavailable" copy="The browser could not read the canonical capability endpoint. No authority data is shown." /> : showEvidence ? <EvidenceBridge /> : showFixture ? <AuthorityWorkspace selected={selected} onSelect={setSelected} /> : <UnavailableTool title={active} state={browserState} />}
    </main>
    {showFixture ? <Inspector selected={selected} tab={tab} onTab={setTab} /> : <aside aria-label="Sovereign capability status" className="sov-inspector sov-inspector--capability"><div className="inspector-empty"><PanelRightClose /><h2>Canonical Core negotiated</h2><p>{browserState === "AUTH_CONTRACT_REQUIRED" ? "Core reports this capability, but no tenant-bound web-session route exists." : "No canonical result is available for this browser session."}</p></div></aside>}
    <footer aria-label="Sovereign connection status" className="sov-workbench__status" tabIndex={0}><strong>Core negotiation: {negotiation}</strong><span>Sovereign Core: {coreVersion ?? "unknown"}</span><span>{showFixture ? "Development fixture · No live authority" : "Production fixture usage: none"}</span></footer>
  </div>;
}

function AuthorityWorkspace({ selected, onSelect }: { selected: string; onSelect: (value: string) => void }) { return <div className="authority-workspace"><div className="authority-toolbar"><label><Search /><span className="sr-only">Search fixture nodes</span><input placeholder="Search fixture nodes…" /></label><span>Fixture preview</span></div><section className="authority-canvas" aria-label="Fixture authority relationship graph"><div className="zoom-controls"><button aria-label="Zoom in"><ZoomIn /></button><button aria-label="Zoom out"><ZoomOut /></button></div><div className="authority-nodes">{nodes.map((node, index) => <button className={selected === node ? "selected" : ""} key={node} onClick={() => onSelect(node)}><span>{index + 1}</span><strong>{node}</strong><code>{node.toLowerCase()}_fixture_01</code></button>)}</div><div className="fixture-constraint"><ShieldCheck /><strong>Constraint</strong><code>con_fixture_01</code></div></section><section aria-label="Configured fixture trace" className="trace-rail" tabIndex={0}><header><strong>Trace · configured path</strong><span>Fixture values only</span></header><ol>{nodes.map((node, index) => <li className={selected === node ? "active" : ""} key={node}><span>{index + 1}</span><strong>{node}</strong><code>{node.toLowerCase()}_fixture_01</code></li>)}</ol></section></div>; }

function Inspector({ selected, tab, onTab }: { selected: string; tab: string; onTab: (tab: string) => void }) { const tabs = ["Overview", "Relationships", "Configured rules", "Evidence"]; return <aside className="sov-inspector"><header><div><Network /><span><strong>{selected.toLowerCase()}_fixture_01</strong><small>{selected}</small></span></div><span>Development fixture</span></header><div className="inspector-tabs" role="tablist" aria-label="Node inspector sections">{tabs.map((name) => <button role="tab" aria-selected={tab === name} onClick={() => onTab(name)} key={name}>{name}</button>)}</div>{tab === "Overview" ? <div className="inspector-content"><section><h2>Node details</h2><dl><div><dt>Node ID</dt><dd><code>{selected.toLowerCase()}_fixture_01</code></dd></div><div><dt>Type</dt><dd>{selected}</dd></div><div><dt>Source</dt><dd>Development fixture</dd></div></dl></section><section><h2>Expected relationship</h2><p>Configured fixture relationship available for interface development.</p></section><section><h2>Effective relationship</h2><p>Effective relationships are computed by Sovereign Core and are not available in this fixture.</p><strong className="contract-wait"><PanelRightClose /> Tenant-bound web contract required</strong></section></div> : <div className="inspector-empty"><Braces /><h2>{tab}</h2><p>This fixture panel never represents canonical production data.</p></div>}</aside>; }

function UnavailableTool({ title, state }: { title: string; state: string }) { return <section className="sov-tool-unavailable"><PanelRightClose /><h2>{title} is unavailable in this browser session</h2><p>{state === "AUTH_CONTRACT_REQUIRED" ? "Sovereign Core reports this capability, but the published Core does not expose a tenant-bound authenticated web-session route. No direct Core route is called from the browser." : "Canonical capability negotiation does not make this result available. No result is calculated or fabricated in React."}</p><strong>{state === "EXPERIMENTAL" ? "Experimental · browser contract required" : "SOVEREIGN_WEB_AUTH_CONTRACT_GAP"}</strong></section>; }
function NegotiationState({ title, copy }: { title: string; copy: string }) { return <section className="sov-tool-unavailable" role="status"><CircleHelp /><h2>{title}</h2><p>{copy}</p></section>; }
function EvidenceBridge() { return <section className="sov-tool-unavailable"><FileCheck2 /><h2>Evidence remains a separate proof boundary</h2><p>Use the existing tenant-scoped Evidence console for canonical records currently exposed by WhitePact.</p><Link className="wp-button wp-button--secondary" to="/dashboard/evidence">Open Evidence console</Link></section>; }
