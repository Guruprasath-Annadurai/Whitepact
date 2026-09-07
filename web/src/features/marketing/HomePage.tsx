// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { lazy, Suspense, useCallback, useState } from "react";
import { ArrowRight, Check, Code2, FileCheck2, Menu, Power, ShieldCheck, UserRoundCheck, X } from "lucide-react";
import { AccessibleDialog } from "../../components/AccessibleDialog";
import { Brand } from "../../components/Brand";
import { ButtonLink } from "../../components/Button";
import { Seo } from "../../components/Seo";
import { publicAsset } from "../../lib/assets";
import { TrustCoreBoundary } from "../../components/TrustCoreBoundary";
import { PublicFooter } from "./PublicPages";

const TrustCore = lazy(() => import("../../components/TrustCore").then((module) => ({ default: module.TrustCore })));

const nav = [["Platform", "/#platform"], ["MCP Gateway", "/#mcp-gateway"], ["Enterprise", "/#enterprise"], ["Security", "/trust"], ["Developers", "/#developers"], ["Pricing", "/pricing"], ["Docs", "/docs"]] as const;
const scenarios = [
  ["Transfer funds", "agent://finance-agent", "Transfer ₹480,000 to a new beneficiary", "EXCEEDED", "CRITICAL"],
  ["Send sensitive email", "agent://support-agent", "Send customer export to an external address", "LIMITED", "HIGH"],
  ["Delete repository", "agent://release-agent", "Delete the production source repository", "DENIED", "CRITICAL"],
  ["Access customer records", "agent://analyst-agent", "Read restricted customer records", "LIMITED", "HIGH"],
  ["Execute shell command", "agent://ops-agent", "Run an unapproved command on production", "EXCEEDED", "CRITICAL"],
];

function PublicNav() {
  const [open, setOpen] = useState(false);
  return (
    <header className="public-nav">
      <Brand />
      <nav aria-label="Primary navigation" className={open ? "is-open" : ""}>
        {nav.map(([item, href]) => <a key={item} href={href} onClick={() => setOpen(false)}>{item}</a>)}
        <a href="https://github.com/Guruprasath-Annadurai/Whitepact" rel="noreferrer"><Code2 size={16} /> GitHub</a>
      </nav>
      <div className="public-nav__actions"><a href="/login">Sign in</a><ButtonLink to="/signup">Get API Key <ArrowRight size={17} /></ButtonLink></div>
      <button className="nav-toggle" aria-expanded={open} aria-label={open ? "Close menu" : "Open menu"} onClick={() => setOpen(!open)}>{open ? <X /> : <Menu />}</button>
    </header>
  );
}

function GovernanceDemo() {
  const [active, setActive] = useState(0);
  const [inspect, setInspect] = useState(false);
  const closeInspect = useCallback(() => setInspect(false), []);
  const scenario = scenarios[active];
  return (
    <section className="section demo" id="platform" aria-labelledby="demo-title">
      <div className="section-heading"><p>Interactive governance demo · Simulated data</p><h2 id="demo-title">WhitePact Governance Console<span>.</span></h2><span>See how a sample request is evaluated before execution. This is not customer traffic.</span></div>
      <div className="scenario-tabs" role="tablist" aria-label="Demonstration scenarios">
        {scenarios.map((item, index) => <button key={item[0]} role="tab" aria-selected={active === index} onClick={() => setActive(index)}>{item[0]}</button>)}
      </div>
      <div className="console-frame">
        <div className="console-request"><span>{scenario[1]}</span><strong>{scenario[2]}</strong></div>
        <ol className="decision-trace">
          <li><i className="cyan" /><span>Identity</span><strong>VERIFIED</strong></li>
          <li><i className="amber" /><span>Authority</span><strong>{scenario[3]}</strong></li>
          <li><i className="green" /><span>Policy</span><strong>MATCHED</strong></li>
          <li><i className="violet" /><span>Risk</span><strong>{scenario[4]}</strong></li>
        </ol>
        <div className="decision-result"><span>Decision</span><strong>REQUIRE APPROVAL</strong><button onClick={() => setInspect(true)}>Inspect decision <ArrowRight size={17} /></button></div>
      </div>
      {inspect && <AccessibleDialog labelId="decision-record-title" onClose={closeInspect} className="decision-modal"><header><div><span>DEMO RECORD</span><h2 id="decision-record-title">Decision inspection</h2></div><button onClick={closeInspect} aria-label="Close decision inspection"><X /></button></header><dl>{[["Agent", scenario[1].replace("agent://", "")], ["Action", scenario[2]], ["Identity", "VERIFIED"], ["Authority", scenario[3] === "EXCEEDED" ? "₹100,000 LIMIT" : scenario[3]], ["Purpose", active === 0 ? "Vendor payment" : "Declared operational task"], ["Policy", "MATCHED"], ["Risk", scenario[4]], ["Approval", "REQUIRED"], ["Decision", "REQUIRE APPROVAL"], ["Action boundary", "BLOCKED BEFORE EXECUTION"], ["Evidence ID", `demo_evd_${String(active + 1).padStart(4, "0")}`]].map(([term,value])=><div key={term}><dt>{term}</dt><dd>{value}</dd></div>)}</dl><p className="demo-disclosure">Demonstration record only. No production customer or payment data is represented.</p></AccessibleDialog>}
    </section>
  );
}

const layers = [
  ["Identity", "Resolve who or what is requesting action."],
  ["Authority", "Apply explicit scope and authority ceilings."],
  ["Policy", "Evaluate contextual rules at runtime."],
  ["Approvals", "Pause actions that require human control."],
  ["Evidence", "Record a verifiable decision trail."],
];

function PlatformSection() {
  return (
    <section className="section control-plane">
      <div className="layer-stack">{layers.map(([title, copy], index) => <div className="layer" key={title}><span>{String(index + 1).padStart(2, "0")}</span><div><h3>{title}</h3><p>{copy}</p></div></div>)}</div>
      <div className="control-copy"><h2>One control plane<br />for every agent<span>.</span></h2><p>WhitePact unifies identity, authority, policy, approvals, revocation and evidence without hiding enforcement behind a chatbot.</p><a href="#mcp-gateway">See the control path <ArrowRight size={17} /></a></div>
    </section>
  );
}

function McpSection() {
  return (
    <section className="section mcp-section" id="mcp-gateway">
      <div><h2>Govern every tool call<br />at the boundary<span>.</span></h2><p>WhitePact sits between agents and the systems they can change. Requests are scoped, evaluated, enforced and recorded before execution.</p><a href="/docs">Explore MCP Gateway <ArrowRight size={17} /></a></div>
      <div className="gateway-flow"><div>AI Agent</div><ArrowRight /><div className="gateway-core"><img src={publicAsset("whitepact-mark.png")} alt="" />WhitePact</div><ArrowRight /><div>MCP / API / Tools</div><footer><ShieldCheck size={16} /> Identity · scope · policy · evidence</footer></div>
    </section>
  );
}

function EvidenceSection() {
  return (
    <section className="section evidence-section" id="security">
      <div><h2>Evidence that<br />survives scrutiny<span>.</span></h2><p>Every governed decision can be traced to identity, authority, policy, risk, approval and execution outcome.</p><small>Hash-chained tamper evidence detects record changes. It is not immutable against a fully compromised database.</small></div>
      <div className="evidence-table" role="table" aria-label="Evidence record example">
        {["Identity verified", "Authority evaluated", "Policy matched", "Risk assessed", "Approval required", "Decision recorded", "Chain verified"].map((item, i) => <div role="row" key={item}><span role="cell">{String(i + 1).padStart(2, "0")}</span><strong role="cell">{item}</strong><em role="cell"><Check size={15} /> recorded</em></div>)}
      </div>
    </section>
  );
}

function PricingSection() {
  const plans = [["Community", "FREE", "One test key and self-hosted governance"], ["Pro", "PRO", "Production keys, evidence and managed billing"], ["Enterprise", "ENTERPRISE", "SSO, private deployment and contracted support"]];
  return (
    <section className="section pricing" id="pricing"><header><h2>Three truthful paths<br />to governed action<span>.</span></h2><p>Plans map directly to the entitlement model. Paid access activates only after a verified billing event or signed enterprise agreement.</p></header><div className="pricing-rail">{plans.map((plan) => <article key={plan[0]}><h3>{plan[0]}</h3><span>{plan[1]}</span><p>{plan[2]}</p><strong>{plan[0] === "Community" ? "Available open source" : "Contact for current pricing"}</strong></article>)}</div><ButtonLink to="/signup">Get API Key <ArrowRight size={17} /></ButtonLink></section>
  );
}

function ProductClosureSections() { return <>
  <section className="section feature-ledger" aria-labelledby="passport-title"><article><UserRoundCheck /><p>Agent Passport</p><h2 id="passport-title">Identity travels with authority<span>.</span></h2><span>Bind each workload to a verified principal, declared purpose, authority ceiling and revocation state before runtime access.</span></article><article><Power /><p>Revocation and kill switch</p><h2>Stop authority before the next action<span>.</span></h2><span>Revoke credentials and authority without waiting for an agent session to end. Enforcement happens at the action boundary.</span></article></section>
  <section className="section comparison" aria-labelledby="comparison-title"><header><p>Deployment choice</p><h2 id="comparison-title">Open source control.<br />Managed operational path<span>.</span></h2></header><div><article><Code2 /><h3>Community</h3><p>Run the MIT-licensed core in your environment. You own infrastructure, data operations and availability.</p></article><article><ShieldCheck /><h3>WhitePact Cloud</h3><p>Use hosted identity, API keys, billing and governance surfaces when the production service and your entitlement are active.</p></article></div></section>
  <section className="section developer-entry" id="developers"><div><p>Developers</p><h2>One boundary.<br />API or MCP<span>.</span></h2><span>Start with a scoped test credential and submit governed requests from server-side code or an MCP client.</span></div><div className="developer-steps"><p><strong>01</strong>Create a test key in your organization.</p><p><strong>02</strong>Connect a server or MCP client.</p><p><strong>03</strong>Inspect the decision and evidence.</p><a href="/docs">Open developer documentation <ArrowRight /></a></div></section>
  <section className="section enterprise-section" id="enterprise"><div><p>Enterprise</p><h2>Private control<br />without false assurance<span>.</span></h2><span>Enterprise architecture can include SSO, private deployment and contracted support. SOC 2 and ISO 27001 certification are not currently claimed.</span></div><div className="enterprise-list">{["OIDC and SAML integration paths", "Tenant-scoped identities and machine credentials", "Private deployment architecture", "Documented security and assurance boundaries"].map(item=><p key={item}><Check />{item}</p>)}<a href="/contact">Discuss enterprise architecture <ArrowRight /></a></div></section>
  <section className="section trust-entry"><div><FileCheck2 /><h2>Trust is a record,<br />not a badge<span>.</span></h2><p>Review implemented controls, OpenSSF evidence, external-review status and known limitations without certification theatre.</p></div><a className="wp-button wp-button--secondary" href="/trust">Open Trust Center <ArrowRight /></a></section>
  </>; }

export function HomePage() {
  return (
    <div className="marketing-page">
      <Seo title="WhitePact | The Trust Layer Between AI and Action" description="Runtime governance for autonomous intelligence across identity, authority, purpose, policy, risk, approval, decision and evidence." />
      <PublicNav />
      <main>
        <section className="hero">
          <div className="hero-copy"><h1>AI agents can act.<br /><span>WhitePact decides<br />whether they should.</span></h1><p>Runtime trust infrastructure for autonomous AI.<br />Identity, authority, policy, approvals, revocation and verifiable evidence across MCP, APIs and agent workflows.</p><div className="hero-actions"><ButtonLink to="/signup">Get API Key <ArrowRight size={18} /></ButtonLink><a className="wp-button wp-button--secondary" href="https://github.com/Guruprasath-Annadurai/Whitepact#quick-start">Run WhitePact locally</a></div><a className="text-link" href="https://github.com/Guruprasath-Annadurai/Whitepact">View on GitHub <ArrowRight size={15} /></a></div>
          <TrustCoreBoundary><Suspense fallback={<div className="trust-core trust-core--loading" role="status" aria-label="Loading Trust Core" />}><TrustCore /></Suspense></TrustCoreBoundary>
        </section>
        <GovernanceDemo /><PlatformSection /><McpSection /><EvidenceSection /><ProductClosureSections /><PricingSection />
        <section className="final-cta"><h2>Put WhitePact between your agents<br />and the real world<span>.</span></h2><ButtonLink to="/signup">Get API Key <ArrowRight size={18} /></ButtonLink></section>
      </main>
      <PublicFooter />
    </div>
  );
}
