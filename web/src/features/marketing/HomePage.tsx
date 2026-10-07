// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { useCallback, useState } from "react";
import { ArrowRight, Check, Code2, FileCheck2, ShieldCheck, X } from "lucide-react";
import { AccessibleDialog } from "../../components/AccessibleDialog";
import { CorporateNav } from "../../components/CorporateNav";
import commerce from "../../content/commerce.json";
import { controlChain } from "../../content/control-chain";
import { ButtonLink } from "../../components/Button";
import { Seo } from "../../components/Seo";
import { publicAsset } from "../../lib/assets";
import { PublicFooter } from "./PublicPages";
import { PricingCards } from "./PricingCards";

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
  <section className="section comparison" aria-labelledby="comparison-title"><header><p>Deployment choice</p><h2 id="comparison-title">Open source control.<br />Managed operational path<span>.</span></h2></header><div><article><Code2 /><h3>Community</h3><p>Run the MIT-licensed core in your environment. You own infrastructure, data operations and availability.</p></article><article><ShieldCheck /><h3>WhitePact Cloud</h3><p>Use hosted identity, API keys, billing and governance surfaces when the production service and your entitlement are active.</p></article></div></section>
  <section className="section developer-entry" id="developers"><div><p>Developers</p><h2>One boundary.<br />API or MCP<span>.</span></h2><span>Follow local setup first. A scoped test credential authenticates requests; independent backend authority and consent are still required.</span></div><div className="developer-steps"><p><strong>01</strong>Create a test key in your organization.</p><p><strong>02</strong>Connect a server or MCP client.</p><p><strong>03</strong>Inspect the decision and evidence.</p><a href="/docs">Open developer documentation <ArrowRight /></a></div></section>
  <section className="section enterprise-section" id="enterprise"><div><p>Enterprise evaluation</p><h2>Know what is enforced.<br />Know what you operate<span>.</span></h2><span>Review identity lifecycle, approval separation, evidence and deployment responsibility. SSO and SCIM require deployment-specific qualification. SOC 2 and ISO 27001 certification are not currently claimed.</span></div><div className="enterprise-list">{["Identity and tenant-boundary review", "Scope, revocation and approval review", "Deployment and operational responsibility", "Assurance evidence and known limitations"].map(item=><p key={item}><Check aria-hidden="true" />{item}</p>)}<a href="/enterprise">Review the enterprise checklist <ArrowRight /></a></div></section>
  <section className="section trust-entry"><div><FileCheck2 /><h2>Trust is a record,<br />not a badge<span>.</span></h2><p>Review implemented controls, OpenSSF evidence, external-review status and known limitations without certification theatre.</p></div><a className="wp-button wp-button--secondary" href="/trust">Open Trust Center <ArrowRight /></a></section>
  </>; }

export function HomePage() {
  return (
    <div className="marketing-page">
      <Seo title={commerce.home.title} description={commerce.home.description} />
      <CorporateNav />
      <main id="main-content" tabIndex={-1}>
        <section className="hero corporate-hero">
          <div className="hero-copy"><p className="hero-category">Independent runtime authority</p><h1>Before an agent acts,<br /><span>verify its authority.</span></h1><p>WhitePact evaluates whether an AI-agent action is authorized before supported execution paths proceed. Knowing who an agent is—and what it wants—is not permission to act.</p><div className="hero-actions"><ButtonLink to="/docs">Start with the docs <ArrowRight size={18} /></ButtonLink><a className="wp-button wp-button--secondary" href="https://github.com/Guruprasath-Annadurai/Whitepact">View GitHub <ArrowRight size={18} /></a></div><p className="hero-availability">Evaluate the source locally. Hosted availability requires separate verification.</p></div>
          <BoundaryIllustration />
        </section>
        <section className="section doctrine-band" aria-label="WhitePact doctrine"><p>Operating doctrine: an agent may think and plan freely. Consequential actions routed through supported, configured WhitePact enforcement paths require independently evaluated authority. Direct calls outside those paths and compromised infrastructure are not universally controlled.</p><a className="text-link" href="/architecture">Understand the boundary <ArrowRight size={17} /></a></section>
        <section className="section authorization-primer" aria-labelledby="primer-title"><div className="section-heading"><p>Different questions. Different controls.</p><h2 id="primer-title">Authentication is a beginning.<br />Not an execution decision.</h2><span>Prompt-layer guardrails inspect content. Runtime authority determines whether a specific principal may perform a specific action now.</span></div><dl>{[
          ["Authentication", "Who is making the request?", "A credential establishes identity, not permission."],
          ["Intent", "What action is being attempted?", "An agent's plan is an input, never an authorization."],
          ["Policy", "What rules apply?", "Evaluate the configured context and constraints."],
          ["Authority", "Is this action permitted now?", "Scope, delegation, consent and revocation must be valid."],
          ["Approval", "Does this instance need human review?", "An approval cannot repair absent authority."],
          ["Execution grant", "What exactly may proceed?", "Scope and time bounds apply on supported guarded paths."],
          ["Evidence", "What happened, and why?", "Record known outcomes. Preserve uncertainty as UNKNOWN."],
        ].map(([term, question, copy]) => <div key={term}><dt>{term}</dt><dd><strong>{question}</strong><p>{copy}</p></dd></div>)}</dl></section>
        <PlatformSection /><AuthorityBoundarySection /><GovernanceDemo />
        <section className="section grant-lifecycle" aria-labelledby="grant-title"><div className="section-heading"><p>Approval is not execution</p><h2 id="grant-title">A bounded grant.<br />A guarded admission.</h2><span>On supported paths, judgment precedes a scoped, short-lived execution grant. The execution boundary—not the browser—checks whether it may still be used.</span></div><ol aria-label="Conceptual execution grant lifecycle">{[["Evaluate", "Resolve current authority and applicable constraints."], ["Review", "Wait for authorized approvers when required."], ["Admit", "Check binding, scope, expiry and current validity."], ["Record", "Return evidence of the known outcome; reconcile UNKNOWN."]].map(([title, copy]) => <li key={title}><h3>{title}</h3><p>{copy}</p></li>)}</ol><p>Conceptual illustration. Inspect the selected adapter contract: not every integration provides the same isolation or lifecycle behavior. Revocation cannot reverse an effect already completed.</p></section>
        <McpSection /><EvidenceSection /><ProductClosureSections /><PricingSection />
        <section className="final-cta"><p className="page-kicker">Start with a supported path</p><h2>Bring authority to<br />your agent architecture<span>.</span></h2><p>Review the integration and its limits before connecting consequential tools.</p><div className="hero-actions"><ButtonLink to="/docs">Read the docs <ArrowRight size={18} /></ButtonLink><ButtonLink to="/contact" variant="secondary">Request evaluation <ArrowRight size={18} /></ButtonLink></div></section>
      </main>
      <PublicFooter />
    </div>
  );
}

function BoundaryIllustration() {
  return <figure className="authority-boundary" aria-labelledby="boundary-caption"><figcaption id="boundary-caption">Agent intent → consequential execution <span>Conceptual boundary · not a live decision</span></figcaption><ol>
    <li className="boundary-request"><span>01 · Agent intent</span><strong>Requested action</strong><p>Principal · purpose · target · arguments</p></li>
    <li className="boundary-evaluation"><span>02 · WhitePact</span><strong>Independent authority evaluation</strong><ul><li>Identity &amp; consent</li><li>Authority &amp; policy</li><li>Risk &amp; approval</li></ul><p>Judgment → scoped execution grant</p></li>
    <li className="boundary-effect"><span>03 · Supported execution path</span><strong>Guarded action admission</strong><p>Tool / system → outcome &amp; evidence</p></li>
  </ol><div className="boundary-outcomes"><span>Denied: no execution</span><span>Approval: wait</span><span>UNKNOWN: reconcile</span></div><p>Direct paths outside this boundary are not automatically governed.</p></figure>;
}
