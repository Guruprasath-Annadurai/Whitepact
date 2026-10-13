// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { lazy, Suspense, useCallback, useState } from "react";
import { ArrowRight, Check, Code2, FileCheck2, Power, ShieldCheck, UserRoundCheck, X } from "lucide-react";
import { AccessibleDialog } from "../../components/AccessibleDialog";
import { CorporateNav } from "../../components/CorporateNav";
import commerce from "../../content/commerce.json";
import { controlChain } from "../../content/control-chain";
import { ButtonLink } from "../../components/Button";
import { Seo } from "../../components/Seo";
import { publicAsset } from "../../lib/assets";
import { TrustCoreBoundary } from "../../components/TrustCoreBoundary";
import { PublicFooter } from "./PublicPages";
import { PricingCards } from "./PricingCards";

const TrustCore = lazy(() => import("../../components/TrustCore").then((module) => ({ default: module.TrustCore })));

const scenarios = [
  ["Transfer funds", "agent://finance-agent", "Transfer ₹480,000 to a new beneficiary", "EXCEEDED", "CRITICAL"],
  ["Send sensitive email", "agent://support-agent", "Send customer export to an external address", "LIMITED", "HIGH"],
  ["Delete repository", "agent://release-agent", "Delete the production source repository", "DENIED", "CRITICAL"],
  ["Access customer records", "agent://analyst-agent", "Read restricted customer records", "LIMITED", "HIGH"],
  ["Execute shell command", "agent://ops-agent", "Run an unapproved command on production", "EXCEEDED", "CRITICAL"],
];

function GovernanceDemo() {
  const [active, setActive] = useState(0);
  const [inspect, setInspect] = useState(false);
  const closeInspect = useCallback(() => setInspect(false), []);
  const scenario = scenarios[active];
  const denied = scenario[3] === "DENIED" || scenario[3] === "EXCEEDED";
  const decision = denied ? "DENIED" : "REQUIRE APPROVAL";
  return (
    <section className="section demo" id="platform" aria-labelledby="demo-title">
      <div className="section-heading"><p>Interactive governance demo · Simulated data</p><h2 id="demo-title">WhitePact Governance Console<span>.</span></h2><span>See how a sample request is evaluated before execution. This is not customer traffic.</span></div>
      <div className="scenario-tabs" role="tablist" aria-label="Demonstration scenarios">
        {scenarios.map((item, index) => <button key={item[0]} id={`scenario-${index}`} role="tab" tabIndex={active === index ? 0 : -1} aria-controls="scenario-panel" aria-selected={active === index} onClick={() => setActive(index)} onKeyDown={(event) => { const next = event.key === "ArrowRight" ? (index + 1) % scenarios.length : event.key === "ArrowLeft" ? (index + scenarios.length - 1) % scenarios.length : event.key === "Home" ? 0 : event.key === "End" ? scenarios.length - 1 : null; if (next !== null) { event.preventDefault(); setActive(next); document.getElementById(`scenario-${next}`)?.focus(); } }}>{item[0]}</button>)}
      </div>
      <div className="console-frame" id="scenario-panel" role="tabpanel" aria-labelledby={`scenario-${active}`}>
        <div className="console-request"><span>{scenario[1]}</span><strong>{scenario[2]}</strong></div>
        <ol className="decision-trace">
          <li><i className="cyan" /><span>Identity</span><strong>VERIFIED</strong></li>
          <li><i className="amber" /><span>Authority</span><strong>{scenario[3]}</strong></li>
          <li><i className="green" /><span>Policy</span><strong>MATCHED</strong></li>
          <li><i className="violet" /><span>Risk</span><strong>{scenario[4]}</strong></li>
        </ol>
        <div className="decision-result"><span>Decision</span><strong>{decision}</strong><button onClick={() => setInspect(true)}>Inspect decision <ArrowRight size={17} /></button></div>
      </div>
      {inspect && <AccessibleDialog labelId="decision-record-title" onClose={closeInspect} className="decision-modal"><header><div><span>DEMO RECORD</span><h2 id="decision-record-title">Decision inspection</h2></div><button onClick={closeInspect} aria-label="Close decision inspection"><X /></button></header><dl>{[["Agent", scenario[1].replace("agent://", "")], ["Action", scenario[2]], ["Identity", "VERIFIED"], ["Authority", scenario[3] === "EXCEEDED" ? "₹100,000 LIMIT" : scenario[3]], ["Purpose", active === 0 ? "Vendor payment" : "Declared operational task"], ["Policy", "MATCHED"], ["Risk", scenario[4]], ["Approval", denied ? "NOT AVAILABLE FOR DENIED AUTHORITY" : "REQUIRED"], ["Decision", decision], ["Simulated result", "Blocked before execution"], ["Evidence ID", `demo_evd_${String(active + 1).padStart(4, "0")}`]].map(([term,value])=><div key={term}><dt>{term}</dt><dd>{value}</dd></div>)}</dl><p className="demo-disclosure">Demonstration record only. No production customer or payment data is represented.</p></AccessibleDialog>}
    </section>
  );
}

const layers = [
  ["Identity", "Resolve who or what is requesting action."],
  ["Authority", "Apply explicit scope and authority ceilings."],
  ["Policy", "Evaluate contextual rules at runtime."],
  ["Approvals", "Pause actions that require human control."],
  ["Evidence", "Record a tenant-scoped, hash-chained decision trail."],
];

function PlatformSection() {
  return (
    <section className="section control-plane">
      <div className="layer-stack">{layers.map(([title, copy], index) => <div className="layer" key={title}><span>{String(index + 1).padStart(2, "0")}</span><div><h3>{title}</h3><p>{copy}</p></div></div>)}</div>
      <div className="control-copy"><h2>One control plane<br />for connected agents<span>.</span></h2><p>WhitePact unifies identity, authority, policy, approvals, revocation and evidence for actions routed through configured enforcement paths.</p><a href="#mcp-gateway">See the control path <ArrowRight size={17} /></a></div>
    </section>
  );
}

function AuthorityBoundarySection() {
  return <section className="section" aria-labelledby="boundary-title"><div className="section-heading"><p>Intent is not permission</p><h2 id="boundary-title">Evaluate before the effect.<br />Enforce at the supported boundary.</h2><span>A prompt filter can evaluate content; it does not independently authorize a consequential action. Authentication identifies the caller. WhitePact separates these from configured runtime authority checks.</span></div><ol className="conceptual-chain" aria-label="Conceptual control chain">{controlChain.map(stage => <li key={stage}>{stage}</li>)}</ol><p>Conceptual map, not a claim that every adapter invokes every subsystem. Approval is not execution. Judgment and scoped, time-bound grants are enforced only through the supported execution path. Isolation depends on deployment; direct alternative paths remain an integration responsibility.</p><a className="text-link" href="/architecture">Understand judgment, grants and failure boundaries <ArrowRight size={17} /></a></section>;
}

function McpSection() {
  return (
    <section className="section mcp-section" id="mcp-gateway">
      <div><h2>Govern supported tool calls<br />at the boundary<span>.</span></h2><p>For integrations routed through WhitePact, requests are scoped, evaluated and recorded before configured execution paths proceed.</p><a href="/docs">Explore MCP Gateway <ArrowRight size={17} /></a></div>
      <div className="gateway-flow"><div>AI Agent</div><ArrowRight /><div className="gateway-core"><img src={publicAsset("whitepact-mark.png")} alt="" />WhitePact</div><ArrowRight /><div>MCP / API / Tools</div><footer><ShieldCheck size={16} /> Identity · scope · policy · evidence</footer></div>
    </section>
  );
}

function EvidenceSection() {
  return (
    <section className="section evidence-section" id="security">
      <div><h2>Evidence with<br />documented boundaries<span>.</span></h2><p>Decisions processed through configured WhitePact enforcement paths produce tenant-scoped records of the context returned by the governance service.</p><small>Illustrative record only, not live evidence. Hash-chain verification has documented boundaries and is not immutable against a fully compromised database.</small></div>
      <div className="evidence-table" role="table" aria-label="Evidence record example">
        {["Identity verified", "Authority evaluated", "Policy matched", "Risk assessed", "Approval required", "Decision recorded", "Verification example"].map((item, i) => <div role="row" key={item}><span role="cell">{String(i + 1).padStart(2, "0")}</span><strong role="cell">{item}</strong><em role="cell"><Check size={15} /> example</em></div>)}
      </div>
    </section>
  );
}

function PricingSection() {
  return (
    <section className="section pricing" id="pricing"><header><h2>Open source first.<br />Choose your operating model<span>.</span></h2><p>Community source is available for evaluation. Hosted pricing and operational availability require confirmation; no paid offer is implied.</p></header><PricingCards /><ButtonLink to="/pricing">Pricing and availability <ArrowRight size={17} /></ButtonLink></section>
  );
}

function ProductClosureSections() { return <>
  <section className="section feature-ledger" aria-labelledby="passport-title"><article><UserRoundCheck /><p>Agent Passport</p><h2 id="passport-title">Identity is not authority<span>.</span></h2><span>Bind each workload to a verified principal, declared purpose, authority ceiling and revocation state before runtime access.</span></article><article><Power /><p>Revocation and kill switch</p><h2>Stop authority before the next action<span>.</span></h2><span>Revoke credentials and authority without waiting for an agent session to end. Enforcement happens at the action boundary.</span></article></section>
  <section className="section comparison" aria-labelledby="comparison-title"><header><p>Deployment choice</p><h2 id="comparison-title">Open source control.<br />Managed operational path<span>.</span></h2></header><div><article><Code2 /><h3>Community</h3><p>Run the MIT-licensed core in your environment. You own infrastructure, data operations and availability.</p></article><article><ShieldCheck /><h3>WhitePact Cloud</h3><p>Use hosted identity, API keys, billing and governance surfaces when the production service and your entitlement are active.</p></article></div></section>
  <section className="section developer-entry" id="developers"><div><p>Developers</p><h2>One boundary.<br />API or MCP<span>.</span></h2><span>Follow local setup first. A scoped test credential authenticates requests; independent backend authority and consent are still required.</span></div><div className="developer-steps"><p><strong>01</strong>Create a test key in your organization.</p><p><strong>02</strong>Connect a server or MCP client.</p><p><strong>03</strong>Inspect the decision and evidence.</p><a href="/docs">Open developer documentation <ArrowRight /></a></div></section>
  <section className="section enterprise-section" id="enterprise"><div><p>Enterprise</p><h2>Private control<br />without false assurance<span>.</span></h2><span>Evaluate private or self-hosted deployment and negotiated support. SSO and SCIM production availability are not promised. SOC 2 and ISO 27001 certification are not currently claimed.</span></div><div className="enterprise-list">{["Identity integration requirements review", "Tenant and credential requirements review", "Private deployment architecture", "Documented security and assurance boundaries"].map(item=><p key={item}><Check />{item}</p>)}<a href="/contact">Discuss enterprise architecture <ArrowRight /></a></div></section>
  <section className="section trust-entry"><div><FileCheck2 /><h2>Trust is a record,<br />not a badge<span>.</span></h2><p>Review implemented controls, OpenSSF evidence, external-review status and known limitations without certification theatre.</p></div><a className="wp-button wp-button--secondary" href="/trust">Open Trust Center <ArrowRight /></a></section>
  </>; }

export function HomePage() {
  return (
    <div className="marketing-page">
      <Seo title={commerce.home.title} description={commerce.home.description} />
      <CorporateNav />
      <main id="main-content" tabIndex={-1}>
        <section className="hero">
          <div className="hero-copy"><h1>AI agents can plan.<br /><span>Authority must be<br />independently enforced.</span></h1><p>An independent pre-execution runtime authorization boundary for supported, configured agent actions. Authentication and intent alone do not authorize execution.</p><div className="hero-actions"><ButtonLink to="/docs">Start with the docs <ArrowRight size={18} /></ButtonLink><a className="wp-button wp-button--secondary" href="https://github.com/Guruprasath-Annadurai/Whitepact#quick-start">Run WhitePact locally</a></div><a className="text-link" href="https://github.com/Guruprasath-Annadurai/Whitepact">View on GitHub <ArrowRight size={15} /></a></div>
          <DeferredTrustCore />
        </section>
        <section className="section"><p className="page-lead">The agent may think freely. It may plan freely. But it cannot act outside independently enforced authority.</p><a className="text-link" href="/architecture">Review the conceptual control chain <ArrowRight size={17} /></a></section>
        <GovernanceDemo /><PlatformSection /><AuthorityBoundarySection /><McpSection /><EvidenceSection /><ProductClosureSections /><PricingSection />
        <section className="final-cta"><h2>Route supported agent actions through<br />WhitePact controls<span>.</span></h2><ButtonLink to="/docs">Start locally <ArrowRight size={18} /></ButtonLink></section>
      </main>
      <PublicFooter />
    </div>
  );
}

function DeferredTrustCore() {
  const [enabled, setEnabled] = useState(false);
  const fallback = <div className="trust-core-static" role="img" aria-label="WhitePact Trust Core illustration"><img src={publicAsset("trust-core-head.webp")} alt="" /></div>;
  return <div className="trust-core-deferred">{enabled ? <TrustCoreBoundary><Suspense fallback={fallback}><TrustCore /></Suspense></TrustCoreBoundary> : <>{fallback}<button className="optional-core" onClick={() => { if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches && window.matchMedia("(min-width: 821px)").matches) setEnabled(true); }}>Enable optional 3D illustration</button></>}</div>;
}
