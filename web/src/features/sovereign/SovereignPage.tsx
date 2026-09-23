// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { ArrowRight, Binary, Clock3, FileCheck2, Network, Radar, Route, ScanSearch, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { Brand } from "../../components/Brand";
import { Seo } from "../../components/Seo";
import { PublicFooter } from "../marketing/PublicPages";

const stages = ["Identity", "Authority", "Policy", "Risk", "Approval", "Decision", "Evidence"];

function SovereignPreview() {
  return <div className="sov-preview" aria-label="Sovereign Authority Lens preview">
    <header><strong>Authority Lens</strong><span>Fixture preview</span></header>
    <div className="sov-preview__flow">{stages.map((stage, index) => <div className={stage === "Authority" ? "is-selected" : ""} key={stage}><span>{index + 1}</span><strong>{stage}</strong></div>)}</div>
    <section><div><h2>Authority</h2><p>Inspect configured relationships and supporting evidence.</p></div><dl><div><dt>Source</dt><dd>Development fixture</dd></div><div><dt>Live source</dt><dd>Authenticated Sovereign Core</dd></div></dl></section>
  </div>;
}

export function SovereignPage() {
  return <div className="sovereign-public"><Seo title="WhitePact Sovereign | Authority analysis workbench" description="Inspect configured authority relationships and supporting evidence with WhitePact Sovereign." path="/sovereign" />
    <header className="sov-public-nav"><Brand /><nav aria-label="Sovereign page navigation"><Link to="/">Product</Link><Link aria-current="page" to="/sovereign">Sovereign</Link><Link to="/trust">Trust</Link><Link to="/docs">Docs</Link><Link to="/pricing">Pricing</Link></nav><div><Link to="/login">Sign in</Link><Link className="wp-button wp-button--primary" to="/sovereign/workbench">Explore Sovereign <ArrowRight aria-hidden="true" /></Link></div></header>
    <main>
      <section className="sov-hero"><div><h1>See authority before it becomes action.</h1><p>WhitePact Sovereign gives teams a clear way to inspect configured authority relationships, trace decisions, and connect them to evidence.</p><div className="hero-actions"><Link className="wp-button wp-button--primary" to="/sovereign/workbench">Explore Sovereign <ArrowRight aria-hidden="true" /></Link><a className="wp-button wp-button--secondary" href="#architecture">Read the architecture</a></div></div><SovereignPreview /></section>
      <section id="architecture" className="sov-band sov-lens"><div><h2>Authority Lens</h2><p>Follow a configured path from identity to evidence. Select a relationship to inspect its source, dependencies, and current contract boundary.</p><Link to="/sovereign/workbench">Open Authority Lens <ArrowRight aria-hidden="true" /></Link></div><div className="sov-principles"><article><Network /><h3>Visualize relationships</h3><p>See how configured identity, authority, policy, risk, approval, decision, and evidence records connect.</p></article><article><ScanSearch /><h3>Inspect details</h3><p>Open a node to view only the fields supplied by its current source.</p></article><article><Route /><h3>Follow the chain</h3><p>Move from a configured relationship to available supporting evidence.</p></article></div></section>
      <section className="sov-band sov-comparison"><div><h2>Declared vs Effective</h2><p>Compare manifest-declared expectations with effective authority evaluated by Sovereign Core through authenticated tenant-derived routes.</p></div><div className="comparison-rails"><article><span>Declared expectation · manifest input</span><pre>{`identity: svc-payments\naction: payments.execute\npolicy: require-approval`}</pre></article><article><span>Effective authority · Core output</span><strong>Available after authentication</strong><p>The browser displays canonical Core output without treating the manifest as authority.</p></article></div></section>
      <section className="sov-band sov-debug"><div><h2>Debugger and Trace</h2><p>Step through the seven-stage governance path without turning the interface into an authority source.</p></div><ol>{stages.map((stage, index) => <li key={stage}><span>{index + 1}</span><strong>{stage}</strong><small>{index === 0 ? "Configured source" : "Inspect when supplied"}</small></li>)}</ol></section>
      <section className="sov-capabilities" aria-label="Sovereign capabilities"><LiveCapability icon={Radar} title="Blast Radius" copy="Project potential impact through the canonical zero-effect simulation route." /><LiveCapability icon={Binary} title="Mission Simulator" copy="Evaluate projected mission steps without executing external actions." /><div className="capability-list"><Capability icon={ShieldCheck} title="Gauntlet" /><Capability icon={FileCheck2} title="Flight Recorder" /><Capability icon={Clock3} title="Time Machine" /></div></section>
      <section className="sov-band sov-evidence"><div><h2>Evidence integration</h2><p>Sovereign connects analysis to WhitePact’s existing tenant-scoped evidence surface. Evidence remains proof material, never execution authority.</p></div><div><Link className="wp-button wp-button--secondary" to="/dashboard/evidence">Open Evidence Explorer <ArrowRight /></Link><Link className="wp-button wp-button--secondary" to="/trust">Review trust boundaries</Link></div></section>
      <section className="sov-final"><h2>Build authority with clarity.</h2><p>Sign in to use the tenant-derived Sovereign Workbench. Production errors remain errors; the interface never falls back to fixture authority.</p><Link className="wp-button wp-button--primary" to="/sovereign/workbench">Explore Sovereign <ArrowRight /></Link></section>
    </main><PublicFooter />
  </div>;
}

function LiveCapability({ icon: Icon, title, copy }: { icon: typeof Radar; title: string; copy: string }) { return <article className="sov-unavailable"><Icon /><h2>{title}</h2><strong>Authenticated live route</strong><span>Zero-effect analysis</span><p>{copy}</p></article>; }
function Capability({ icon: Icon, title }: { icon: typeof ShieldCheck; title: string }) { return <article><Icon /><div><h3>{title}</h3><p>Canonical results are available through the authenticated Workbench.</p></div><ArrowRight /></article>; }
