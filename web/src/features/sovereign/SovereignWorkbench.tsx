// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { useState } from "react";
import { Binary, Braces, ChevronLeft, CircleHelp, Clock3, FileCheck2, GitCompareArrows, Menu, Network, PanelRightClose, Radar, Route, ScanSearch, Search, ShieldCheck, X, ZoomIn, ZoomOut } from "lucide-react";
import { Link } from "react-router-dom";
import { Brand } from "../../components/Brand";
import { Seo } from "../../components/Seo";

const tools = [
  ["Authority Lens", Network], ["Expected vs Effective", GitCompareArrows], ["Debugger", ScanSearch], ["Trace", Route], ["Blast Radius", Radar], ["Mission Simulator", Binary], ["Gauntlet", ShieldCheck], ["Flight Recorder", FileCheck2], ["Time Machine", Clock3], ["Evidence Explorer", Braces],
] as const;
const nodes = ["Identity", "Authority", "Policy", "Risk", "Approval", "Decision", "Evidence"];

export function SovereignWorkbench() {
  const [active, setActive] = useState("Authority Lens");
  const [selected, setSelected] = useState("Authority");
  const [tab, setTab] = useState("Overview");
  const [notice, setNotice] = useState(true);
  const [sidebar, setSidebar] = useState(false);
  const unavailable = active !== "Authority Lens" && active !== "Evidence Explorer";
  return <div className="sov-workbench"><Seo title="Sovereign Workbench | WhitePact" description="Fixture-only WhitePact Sovereign Workbench preview." path="/sovereign/workbench" noIndex />
    <header className="sov-workbench__top"><button className="sov-mobile-toggle" onClick={() => setSidebar(true)} aria-label="Open Sovereign navigation"><Menu /></button><Brand /><span>Sovereign</span><nav><Link to="/dashboard/evidence"><FileCheck2 /> Evidence</Link><Link to="/docs"><CircleHelp /> Help</Link></nav></header>
    <aside aria-label="Sovereign tool navigation" className={sidebar ? "sov-workbench__nav is-open" : "sov-workbench__nav"}><button className="sov-nav-close" onClick={() => setSidebar(false)} aria-label="Close Sovereign navigation"><X /></button><nav aria-label="Sovereign tools">{tools.map(([name, Icon]) => <button className={active === name ? "active" : ""} key={name} onClick={() => { setActive(name); setSidebar(false); }}><Icon /><span>{name}</span></button>)}</nav><Link to="/sovereign"><ChevronLeft /> Product page</Link></aside>
    {sidebar && <button className="sov-workbench__scrim" onClick={() => setSidebar(false)} aria-label="Close Sovereign navigation" />}
    <main className="sov-workbench__main"><header><div><h1>{active}</h1><p>{active === "Authority Lens" ? "Inspect configured authority relationships and supporting evidence." : "This product surface is prepared for a canonical Sovereign Core contract."}</p></div><div className="mode-switch" aria-label="Data mode"><button aria-pressed="true">Fixture preview</button><button disabled>Production</button><span>Unavailable</span></div></header>
      {notice && <section className="fixture-notice" role="status"><CircleHelp /><div><strong>Development fixture — not production authority data</strong><p>This environment contains fixture data for UI and integration development. No production authority result is displayed.</p></div><button onClick={() => setNotice(false)}>Dismiss <X /></button></section>}
      {unavailable ? <UnavailableTool title={active} /> : active === "Evidence Explorer" ? <EvidenceBridge /> : <AuthorityWorkspace selected={selected} onSelect={setSelected} />}
    </main>
    <Inspector selected={selected} tab={tab} onTab={setTab} />
    <footer aria-label="Sovereign connection status" className="sov-workbench__status" tabIndex={0}><strong>Canonical Sovereign contract: unavailable</strong><span>Production data: unavailable</span><span>Development fixture · No live connection</span></footer>
  </div>;
}

function AuthorityWorkspace({ selected, onSelect }: { selected: string; onSelect: (value: string) => void }) { return <div className="authority-workspace"><div className="authority-toolbar"><label><Search /><span className="sr-only">Search fixture nodes</span><input placeholder="Search fixture nodes…" /></label><span>Fixture preview</span></div><section className="authority-canvas" aria-label="Fixture authority relationship graph"><div className="zoom-controls"><button aria-label="Zoom in"><ZoomIn /></button><button aria-label="Zoom out"><ZoomOut /></button></div><div className="authority-nodes">{nodes.map((node, index) => <button className={selected === node ? "selected" : ""} key={node} onClick={() => onSelect(node)}><span>{index + 1}</span><strong>{node}</strong><code>{node.toLowerCase()}_fixture_01</code></button>)}</div><div className="fixture-constraint"><ShieldCheck /><strong>Constraint</strong><code>con_fixture_01</code></div></section><section aria-label="Configured fixture trace" className="trace-rail" tabIndex={0}><header><strong>Trace · configured path</strong><span>Fixture values only</span></header><ol>{nodes.map((node, index) => <li className={selected === node ? "active" : ""} key={node}><span>{index + 1}</span><strong>{node}</strong><code>{node.toLowerCase()}_fixture_01</code></li>)}</ol></section></div>; }

function Inspector({ selected, tab, onTab }: { selected: string; tab: string; onTab: (tab: string) => void }) { const tabs = ["Overview", "Relationships", "Configured rules", "Evidence"]; return <aside className="sov-inspector"><header><div><Network /><span><strong>{selected.toLowerCase()}_fixture_01</strong><small>{selected}</small></span></div><span>Development fixture</span></header><div className="inspector-tabs" role="tablist" aria-label="Node inspector sections">{tabs.map((name) => <button role="tab" aria-selected={tab === name} onClick={() => onTab(name)} key={name}>{name}</button>)}</div>{tab === "Overview" ? <div className="inspector-content"><section><h2>Node details</h2><dl><div><dt>Node ID</dt><dd><code>{selected.toLowerCase()}_fixture_01</code></dd></div><div><dt>Type</dt><dd>{selected}</dd></div><div><dt>Source</dt><dd>Development fixture</dd></div></dl></section><section><h2>Expected relationship</h2><p>Configured fixture relationship available for interface development.</p></section><section><h2>Effective relationship</h2><p>Effective relationships are computed by Sovereign Core and are not available in this fixture.</p><strong className="contract-wait"><PanelRightClose /> Awaiting Sovereign Core contract</strong></section></div> : <div className="inspector-empty"><Braces /><h2>{tab}</h2><p>This panel will display canonical data when its Sovereign Core contract is available.</p></div>}</aside>; }

function UnavailableTool({ title }: { title: string }) { return <section className="sov-tool-unavailable"><PanelRightClose /><h2>{title} is unavailable in production</h2><p>The interface boundary is ready, but WhitePact has no canonical Sovereign Core contract for this capability. No result is calculated or fabricated in React.</p><strong>Awaiting Sovereign Core contract</strong></section>; }
function EvidenceBridge() { return <section className="sov-tool-unavailable"><FileCheck2 /><h2>Evidence remains a separate proof boundary</h2><p>Use the existing tenant-scoped Evidence console for canonical records currently exposed by WhitePact.</p><Link className="wp-button wp-button--secondary" to="/dashboard/evidence">Open Evidence console</Link></section>; }
