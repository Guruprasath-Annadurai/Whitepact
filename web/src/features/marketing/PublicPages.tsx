// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { ArrowLeft, ArrowRight, Check, ExternalLink, Mail, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { Brand } from "../../components/Brand";
import { Seo } from "../../components/Seo";

const legal = {
  terms: {
    title: "Terms of Service",
    description: "The terms governing WhitePact hosted services and open-source software.",
    sections: [
      ["Service scope", "WhitePact provides AI governance software, hosted interfaces and self-hosted open-source components. Paid hosted service availability depends on an active order or subscription."],
      ["Accounts and credentials", "Customers are responsible for authorized account use and safeguarding credentials. Raw API-key secrets are shown once and are not recoverable."],
      ["Acceptable use", "The service may not be used to violate law, access systems without authorization, evade safety controls or harm others."],
      ["Availability and warranties", "Open-source components are provided under the MIT License. Hosted service commitments apply only when stated in an executed agreement."],
      ["Review status", "This document is a repository-maintained draft. Qualified legal counsel review is required before commercial publication."],
    ],
  },
  privacy: {
    title: "Privacy Policy",
    description: "How WhitePact handles account, organization, security and governance data.",
    sections: [
      ["Data collected", "Hosted services may process account identity, organization membership, API-key metadata, security logs, billing references and content submitted for governance evaluation."],
      ["Purpose", "Data is used to provide, secure, support and bill the service, enforce tenant boundaries and produce requested governance evidence."],
      ["Authentication cookies", "The dashboard uses strictly necessary session and CSRF cookies. The current website does not include advertising or cross-site tracking."],
      ["Retention and rights", "Retention and data-subject request commitments are described in the complete policy maintained with the source repository."],
      ["Review status", "This policy is an adopted operating draft but has not been certified by legal counsel. Counsel review remains required."],
    ],
  },
};

function PublicHeader() { return <header className="subpage-nav"><Brand /><nav aria-label="Page navigation"><Link to="/">Home</Link><Link to="/docs">Docs</Link><Link to="/trust">Trust</Link><Link to="/contact">Contact</Link><Link className="wp-button wp-button--primary" to="/signup">Get API Key</Link></nav></header>; }
function PublicFooter() { return <footer className="subpage-footer"><Brand compact /><p>Runtime governance for autonomous intelligence.</p><Link to="/terms">Terms</Link><Link to="/privacy">Privacy</Link><Link to="/contact">Contact</Link></footer>; }

export function LegalPage({ kind }: { kind: keyof typeof legal }) {
  const page = legal[kind];
  return <div className="subpage"><Seo title={`${page.title} | WhitePact`} description={page.description} path={`/${kind}`} /><PublicHeader /><main className="editorial-page"><p className="page-kicker">Legal · Counsel review required</p><h1>{page.title}<span>.</span></h1><p className="page-lead">{page.description}</p><div className="legal-notice"><ShieldCheck />This web version is provided for product transparency and is not represented as lawyer-approved.</div>{page.sections.map(([title, copy], index) => <section key={title}><span>{String(index + 1).padStart(2, "0")}</span><div><h2>{title}</h2><p>{copy}</p></div></section>)}<a className="text-link" href={`https://github.com/Guruprasath-Annadurai/Whitepact/blob/main/${kind === "terms" ? "TERMS_OF_SERVICE.md" : "PRIVACY_POLICY.md"}`}>Read the complete repository document <ExternalLink size={15} /></a></main><PublicFooter /></div>;
}

export function DocsPage() {
  const steps = [["01", "Create a scoped key", "Create a test key in the dashboard. The raw secret is disclosed once."], ["02", "Connect your agent", "Send the key from your server or MCP client. Never embed it in browser code."], ["03", "Submit governed actions", "WhitePact evaluates identity, authority, purpose, policy and risk before action."], ["04", "Verify evidence", "Inspect the resulting decision and its tenant-bound evidence record."]];
  return <div className="subpage"><Seo title="Developer Documentation | WhitePact" description="Integrate WhitePact runtime governance through API and MCP boundaries." path="/docs" /><PublicHeader /><main className="docs-page"><p className="page-kicker">Developer entry</p><h1>Put a decision boundary<br />in front of agent action<span>.</span></h1><p className="page-lead">Start with a scoped test credential, connect your runtime, and preserve evidence for every governed decision.</p><div className="docs-grid">{steps.map(([number,title,copy]) => <article key={number}><span>{number}</span><h2>{title}</h2><p>{copy}</p></article>)}</div><section className="code-entry"><div><h2>API and MCP references</h2><p>The generated API reference documents exact request schemas. The repository quick start covers local and MCP configuration.</p></div><a className="wp-button wp-button--secondary" href="/api/docs">Open API reference <ArrowRight /></a><a className="wp-button wp-button--secondary" href="https://github.com/Guruprasath-Annadurai/Whitepact#quick-start">Repository quick start <ArrowRight /></a></section></main><PublicFooter /></div>;
}

export function AboutPage() { return <div className="subpage"><Seo title="About WhitePact" description="Why WhitePact exists: to keep autonomous action inside explicit human authority." path="/about" /><PublicHeader /><main className="editorial-page"><p className="page-kicker">Company and project</p><h1>Autonomy needs<br />an enforceable pact<span>.</span></h1><p className="page-lead">WhitePact is an open-source-first runtime governance project created to make autonomous systems accountable before they change the world around them.</p>{[["Mission", "Keep agent action inside verified identity, explicit authority, stated purpose, applicable policy and human-approved risk."], ["Operating principle", "Evidence before assertion. A control is described as implemented only when its enforcement path and tests exist."], ["Commercial status", "Community software is available today. Hosted commercial capability is offered only when the required production configuration and agreement are active."]].map(([title,copy],i)=><section key={title}><span>0{i+1}</span><div><h2>{title}</h2><p>{copy}</p></div></section>)}</main><PublicFooter /></div>; }

export function ContactPage() { return <div className="subpage"><Seo title="Contact WhitePact" description="Security, support and enterprise contact paths for WhitePact." path="/contact" /><PublicHeader /><main className="contact-page"><p className="page-kicker">Contact and support</p><h1>Bring the action boundary<br />into your architecture<span>.</span></h1><div className="contact-grid"><article><Mail /><h2>Product and enterprise</h2><p>Architecture evaluation, private deployment and commercial discussions.</p><a href="mailto:annaduraiguruprasath7@gmail.com?subject=WhitePact%20enterprise%20inquiry">Contact WhitePact <ArrowRight /></a></article><article><ShieldCheck /><h2>Security disclosure</h2><p>Report suspected vulnerabilities through the published coordinated disclosure process.</p><a href="/.well-known/security.txt">Security contact <ArrowRight /></a></article><article><ExternalLink /><h2>Open-source support</h2><p>Use GitHub Discussions and Issues for reproducible community questions and defects.</p><a href="https://github.com/Guruprasath-Annadurai/Whitepact">Open repository <ArrowRight /></a></article></div></main><PublicFooter /></div>; }

export function TrustCenterPage() {
  const areas = [["Security architecture", "Layered application, transport and deployment controls."], ["Identity & access", "Human sessions and machine credentials use separate trust paths."], ["Tenant isolation", "Organization scope is enforced in backend data access."], ["API-key security", "One-time disclosure, verifier storage, rotation and revocation."], ["Data protection", "Data minimization, field-encryption support and secure transport requirements."], ["Software supply chain", "Pinned automation, SBOM and provenance-oriented release controls."], ["Vulnerability management", "Coordinated disclosure and repository security checks."], ["Incident response", "Documented reporting and response procedures."], ["OpenSSF evidence", "Repository evidence only; no certification claim."], ["External review", "Independent commercial penetration test is not currently claimed."], ["Assurance status", "SOC 2: not currently certified. ISO 27001: not currently certified."], ["Known limitations", "Hosted production, legal and independent assurance gates are reported separately."]];
  return <div className="subpage trust-page"><Seo title="Trust Center | WhitePact" description="WhitePact security architecture, assurance status and known limitations." path="/trust" /><PublicHeader /><main><p className="page-kicker">Trust Center</p><h1>Controls, evidence<br />and honest boundaries<span>.</span></h1><p className="page-lead">WhitePact distinguishes implemented security controls from external certification and production validation.</p><div className="trust-grid">{areas.map(([title,copy])=><article key={title}><Check /><h2>{title}</h2><p>{copy}</p></article>)}</div></main><PublicFooter /></div>;
}

export function NotFoundPage() { return <div className="subpage"><Seo title="Page not found | WhitePact" description="The requested WhitePact page could not be found." path="/404" noIndex /><PublicHeader /><main className="not-found"><span>404</span><h1>This boundary<br />does not exist.</h1><p>The requested page was not found. Return to the WhitePact control plane.</p><Link className="wp-button wp-button--primary" to="/"><ArrowLeft /> Return home</Link></main><PublicFooter /></div>; }

export function BillingResultPage({ result }: { result: "success" | "cancelled" }) { const success = result === "success"; return <div className="subpage"><Seo title={`Billing ${result} | WhitePact`} description="WhitePact billing status." path={`/billing/${result}`} noIndex /><PublicHeader /><main className="not-found"><span>{success ? "CHECKOUT RETURNED" : "CHECKOUT CANCELLED"}</span><h1>{success ? "Payment received by Stripe." : "No subscription change was made."}</h1><p>{success ? "Your entitlement activates only after WhitePact verifies the signed Stripe webhook. Refresh Billing to see confirmed plan state." : "You can return to Billing whenever you are ready. No access is granted from a redirect alone."}</p><Link className="wp-button wp-button--primary" to="/dashboard/billing">Open billing <ArrowRight /></Link></main><PublicFooter /></div>; }
