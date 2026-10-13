// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { CorporateNav } from "../../components/CorporateNav";
import { Seo } from "../../components/Seo";
import corporate from "../../content/corporate.json";
import { controlChain } from "../../content/control-chain";
import { PublicFooter } from "./PublicPages";

const baseline = "https://github.com/Guruprasath-Annadurai/Whitepact/blob/52d9b3c5497af24bb7d4a7147e33deaadc64296e/";
const developerReferences = [
  ["CLI source", "src/whitepact/cli.py"],
  ["Python governance client", "sdk/python/rai_client/governance.py"],
  ["TypeScript governance source", "sdk/typescript/src/governance.ts"],
  ["Repository setup", "README.md"],
];

const productControls = [
  ["Authority", "A valid identity is not permission.", "Evaluate the principal's current authority for the requested action.", "Keep access and action permission separate.", "Only supported, configured paths are governed."],
  ["Policy", "An agent's plan is not an operating rule.", "Apply the configured policy to the declared action.", "Make restrictions explicit before execution.", "Operators must configure and maintain applicable policy."],
  ["Risk", "Not every action has the same consequence.", "Use the applicable risk assessment in the judgment path.", "Escalate consequential actions where configured.", "Risk assessment is not a guarantee of safety."],
  ["Approval", "Sensitive actions may need another decision maker.", "Persist approval-required requests for authorized resolution.", "Keep human intervention explicit.", "A vote is not a substitute for current authority."],
  ["Judgment", "An evaluation response can be mistaken for permission to act.", "Distinguish denied, approval-required and allowed results.", "Give integrators a decision they must handle deliberately.", "Judgment alone does not enforce a downstream boundary."],
  ["Execution Grants", "Broad credentials can outlive the task they were issued for.", "Bind supported execution authorization to scope and time.", "Constrain what may proceed at the guarded boundary.", "Review the selected runtime contract for grant and admission guarantees."],
  ["Governed Execution", "A tool can be called outside the evaluated path.", "Admit the action through the configured guarded executor.", "Connect authorization to the consequential operation.", "Direct calls outside that path remain outside WhitePact's enforcement scope."],
  ["Revocation", "Permission can change while work is waiting.", "Check current authorization on supported execution paths.", "Invalidate future use when authority is removed.", "Revocation cannot undo an external effect already completed."],
  ["Evidence", "A successful HTTP response does not prove an external effect.", "Record the supported decision and outcome with tenant context.", "Provide an investigation trail, including uncertainty.", "UNKNOWN must be reconciled; evidence is not authority."],
  ["Audit", "Records without context are difficult to evaluate.", "Expose authenticated evidence and documented verification boundaries.", "Support review of what was requested and recorded.", "Hash-linked evidence is not immutable against fully compromised storage."],
];

const architecturePlanes = [
  { title: "Control plane", scope: "Decide whether this action may proceed", controls: controlChain.slice(0, 9), copy: "Identity, authority, declared intent and configured controls inform judgment. Authentication and commercial entitlement never replace action authorization." },
  { title: "Execution plane", scope: "Admit the scoped action", controls: controlChain.slice(9, 11), copy: "The supported guarded boundary connects authorization to execution. Scope, expiry, replay protection and isolation depend on the implemented integration and deployment contract." },
  { title: "Evidence plane", scope: "Record the decision and outcome", controls: controlChain.slice(11, 13), copy: "Tenant-scoped records support investigation and audit. They do not independently prove an external side effect, and UNKNOWN remains uncertainty." },
  { title: "Revocation", scope: "Invalidate future authority", controls: controlChain.slice(13), copy: "Subsequent supported checks use current authorization state. Revocation is not a rollback of completed external effects." },
];

const enterpriseControls = [
  ["Identity, RBAC and member lifecycle", "Implemented · deployment dependent", "Validate the configured human/machine identity paths, role assignment, membership and revocation in your installation."],
  ["SSO, SCIM and MFA", "Deployment dependent", "Confirm supported provider configuration and management contracts. A status page is not proof of enrollment or a provisioned enterprise identity service."],
  ["Approval separation and break-glass", "Contract dependent", "Evaluate authorized approvers, separation of duties and exceptional-access lifecycle against the selected backend contracts; do not infer these from a paid plan."],
  ["Audit, evidence and SIEM", "Implemented evidence · ingestion requires validation", "Review tenant-scoped schemas and the supported ingestion/export path. Establish external-effect reconciliation and retention responsibilities."],
  ["Deployment and operations", "Operator dependent", "Qualify secrets, transport, storage, backup, isolation and incident response in the environment you intend to operate."],
  ["External assurance", "Not externally certified", "SOC 2, ISO 27001, independent commercial penetration testing and uptime commitments are not claimed by this page."],
];

export function CorporatePage({ pageKey }: { pageKey: keyof typeof corporate }) {
  const page = corporate[pageKey];
  return <div className="subpage">
    <Seo title={page.title} description={page.description} path={page.path} />
    <CorporateNav />
    <main id="main-content" tabIndex={-1} className="editorial-page">
      <p className="page-kicker">WhitePact · {pageKey}</p>
      <h1>{page.heading}<span>.</span></h1>
      <p className="page-lead">{page.description}</p>
      <nav className="corporate-page-index" aria-label="On this page">
        {pageKey === "product" && <a href="#product-controls">Product controls</a>}
        {pageKey === "architecture" && <a href="#control-chain-heading">Architecture map</a>}
        {pageKey === "enterprise" && <a href="#enterprise-controls">Evaluation checklist</a>}
        {page.sections.map(([title], index) => <a key={title} href={`#section-${index + 1}`}>{title}</a>)}
      </nav>
      {pageKey === "product" && <section aria-labelledby="product-controls"><span>CONTROL</span><div>
        <h2 id="product-controls">What WhitePact actually does</h2>
        <p>Read each control as an operating behavior, not a blanket guarantee. Expand a control for the problem, benefit and enforcement limit.</p>
        <div className="control-explainers">{productControls.map(([title, problem, behavior, benefit, limit]) => <details key={title}>
          <summary>{title}<span>{behavior}</span></summary>
          <dl><dt>Problem</dt><dd>{problem}</dd><dt>WhitePact behavior</dt><dd>{behavior}</dd><dt>Practical benefit</dt><dd>{benefit}</dd><dt>Boundary</dt><dd>{limit}</dd></dl>
        </details>)}</div>
      </div></section>}
      {pageKey === "architecture" && <section aria-labelledby="control-chain-heading">
        <span>MAP</span><div>
          <h2 id="control-chain-heading">The conceptual control chain</h2>
          <p>This ordered map describes the supported boundary conceptually. It does not assert that every adapter invokes every subsystem, that every deployment provides container isolation or that queued dispatcher work is enabled. Current product contracts and supported configuration govern.</p>
          <div className="architecture-planes" role="group" aria-label="Conceptual runtime authorization control chain">{architecturePlanes.map((plane) => <article key={plane.title}>
            <h3>{plane.title}</h3><p className="architecture-plane-purpose">{plane.scope}</p>
            <ol start={controlChain.indexOf(plane.controls[0]) + 1}>{plane.controls.map((control) => <li key={control}>{control}</li>)}</ol><p>{plane.copy}</p>
          </article>)}</div>
          <p>The complete ordered chain above is a conceptual architecture illustration, not live telemetry or a claim that every adapter invokes every subsystem.</p>
        </div>
      </section>}
      {page.sections.map(([title, copy], index) => <section key={title}>
        <span>{String(index + 1).padStart(2, "0")}</span><div><h2 id={`section-${index + 1}`}>{title}</h2><p>{copy}</p>
          {pageKey === "product" && title === "Sovereign" && <Link className="text-link" to="/sovereign">Explore Sovereign <ArrowRight size={15} /></Link>}
        </div>
      </section>)}
      {pageKey === "enterprise" && <section aria-labelledby="enterprise-controls"><span>REVIEW</span><div>
        <h2 id="enterprise-controls">An evaluation checklist, not a certification badge</h2>
        <p>Use these questions to qualify your deployment. Source implementation, independently qualified engineering, operational acceptance and external certification are different evidence categories.</p>
        <dl className="enterprise-control-list">{enterpriseControls.map(([title, status, copy]) => <div key={title}><dt>{title}</dt><dd><p className="control-status">{status}</p><p>{copy}</p></dd></div>)}</dl>
        <Link className="text-link" to="/trust">Inspect scope and evidence <ArrowRight size={15} /></Link>
      </div></section>}
      {pageKey === "developers" && <section aria-labelledby="developer-source-heading"><span>SRC</span><div>
        <h2 id="developer-source-heading">Review the implementation baseline</h2>
        <p>These source links pin the Phase 1 implementation baseline. Use the generated API reference for the exact deployed schemas; integration references may require a session or API credential.</p>
        <p>The baseline SDK evidence-detail helpers target a route this backend does not provide. Use the supported evidence list or signed-in Evidence console; the docs explain the authentication distinction. Source availability is not proof that every helper works against your server.</p>
        <ul>{developerReferences.map(([label, path]) => <li key={path}><a className="text-link" href={`${baseline}${path}`}>{label} <ArrowRight size={15} /></a></li>)}</ul>
        <Link className="text-link" to="/docs">Read setup and result handling <ArrowRight size={15} /></Link>
        <p><a className="text-link" href="/api/docs">Open deployed API reference <ArrowRight size={15} /></a></p>
      </div></section>}
      {pageKey === "security" && <p><a className="text-link" href={`${baseline}SECURITY.md`}>Security disclosure policy <ArrowRight size={15} /></a></p>}
      {pageKey === "enterprise" && <p><a className="text-link" href={`${baseline}docs/enterprise/LAYER2_IDENTITY_SECURITY.md`}>Review identity implementation scope <ArrowRight size={15} /></a></p>}
      <p><Link className="text-link" to={pageKey === "enterprise" ? "/contact" : pageKey === "security" ? "/trust" : "/docs"}>
        {pageKey === "enterprise" ? "Discuss an evaluation" : pageKey === "security" ? "Review the Trust Center" : "Get started with the docs"} <ArrowRight size={15} />
      </Link></p>
    </main>
    <PublicFooter />
  </div>;
}
