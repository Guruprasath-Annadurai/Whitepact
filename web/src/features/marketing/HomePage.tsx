// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { lazy, Suspense, useState } from "react";
import { ArrowRight, Check, Code2, Menu, ShieldCheck, X } from "lucide-react";
import { Brand } from "../../components/Brand";
import { ButtonLink } from "../../components/Button";
import { publicAsset } from "../../lib/assets";

const TrustCore = lazy(() => import("../../components/TrustCore").then((module) => ({ default: module.TrustCore })));

const nav = ["Platform", "MCP Gateway", "Security", "Developers", "Pricing", "Docs"];
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
        {nav.map((item) => <a key={item} href={`#${item.toLowerCase().replaceAll(" ", "-")}`}>{item}</a>)}
        <a href="https://github.com/Guruprasath-Annadurai/Whitepact" rel="noreferrer"><Code2 size={16} /> GitHub</a>
      </nav>
      <div className="public-nav__actions"><a href="/login">Sign in</a><ButtonLink to="/signup">Get API Key <ArrowRight size={17} /></ButtonLink></div>
      <button className="nav-toggle" aria-expanded={open} aria-label={open ? "Close menu" : "Open menu"} onClick={() => setOpen(!open)}>{open ? <X /> : <Menu />}</button>
    </header>
  );
}

function GovernanceDemo() {
  const [active, setActive] = useState(0);
  const scenario = scenarios[active];
  return (
    <section className="section demo" id="platform" aria-labelledby="demo-title">
      <div className="section-heading"><p>Product demonstration</p><h2 id="demo-title">WhitePact Live Governance Console<span>.</span></h2><span>See how a request is evaluated before execution.</span></div>
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
        <div className="decision-result"><span>Decision</span><strong>REQUIRE APPROVAL</strong><button>Inspect decision <ArrowRight size={17} /></button></div>
      </div>
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
        {["Identity verified", "Authority evaluated", "Policy matched", "Risk assessed", "Approval required", "Decision recorded", "Chain verified"].map((item, i) => <div role="row" key={item}><span>{String(i + 1).padStart(2, "0")}</span><strong>{item}</strong><em><Check size={15} /> recorded</em></div>)}
      </div>
    </section>
  );
}

function PricingSection() {
  const plans = [
    ["Community", "Open source", "Self-hosted local governance"],
    ["Developer", "Experiment & build", "Hosted API access"],
    ["Pro", "Production", "Evidence, multiple keys, webhooks"],
    ["Business", "Advanced operations", "RBAC and longer retention"],
    ["Enterprise", "Mission critical", "SSO, SCIM, private deployment"],
  ];
  return (
    <section className="section pricing" id="pricing"><header><h2>Built for every stage.<br />Engineered for trust<span>.</span></h2><p>Pricing is configuration-driven and shown only when approved plans are active.</p></header><div className="pricing-rail">{plans.map((plan) => <article key={plan[0]}><h3>{plan[0]}</h3><span>{plan[1]}</span><p>{plan[2]}</p><strong>Contact for current pricing</strong></article>)}</div><ButtonLink to="/signup">Get API Key <ArrowRight size={17} /></ButtonLink></section>
  );
}

export function HomePage() {
  return (
    <div className="marketing-page">
      <PublicNav />
      <main>
        <section className="hero">
          <div className="hero-copy"><h1>AI agents can act.<br /><span>WhitePact decides<br />whether they should.</span></h1><p>Runtime trust infrastructure for autonomous AI.<br />Identity, authority, policy, approvals, revocation and verifiable evidence across MCP, APIs and agent workflows.</p><div className="hero-actions"><ButtonLink to="/signup">Get API Key <ArrowRight size={18} /></ButtonLink><a className="wp-button wp-button--secondary" href="https://github.com/Guruprasath-Annadurai/Whitepact#quick-start">Run WhitePact locally</a></div><a className="text-link" href="https://github.com/Guruprasath-Annadurai/Whitepact">View on GitHub <ArrowRight size={15} /></a></div>
          <Suspense fallback={<div className="trust-core trust-core--loading" aria-hidden="true" />}><TrustCore /></Suspense>
        </section>
        <GovernanceDemo /><PlatformSection /><McpSection /><EvidenceSection /><PricingSection />
        <section className="final-cta"><h2>Put WhitePact between your agents<br />and the real world<span>.</span></h2><ButtonLink to="/signup">Get API Key <ArrowRight size={18} /></ButtonLink></section>
      </main>
      <footer className="public-footer"><Brand compact /><p>Runtime governance for autonomous AI.</p><a href="/.well-known/security.txt">Security</a><a href="/trust">Trust Center</a><a href="https://github.com/Guruprasath-Annadurai/Whitepact">GitHub</a></footer>
    </div>
  );
}
