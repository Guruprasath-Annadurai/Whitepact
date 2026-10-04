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

export function CorporatePage({ pageKey }: { pageKey: keyof typeof corporate }) {
  const page = corporate[pageKey];
  return <div className="subpage">
    <Seo title={page.title} description={page.description} path={page.path} />
    <CorporateNav />
    <main id="main-content" tabIndex={-1} className="editorial-page">
      <p className="page-kicker">WhitePact · {pageKey}</p>
      <h1>{page.heading}<span>.</span></h1>
      <p className="page-lead">{page.description}</p>
      {pageKey === "architecture" && <section aria-labelledby="control-chain-heading">
        <span>MAP</span><div>
          <h2 id="control-chain-heading">The conceptual control chain</h2>
          <p>This ordered map describes the supported boundary conceptually. It does not assert that every adapter invokes every subsystem, that every deployment provides container isolation or that queued dispatcher work is enabled. Current product contracts and supported configuration govern.</p>
          <ol aria-label="Conceptual runtime authorization control chain">{controlChain.map((control) => <li key={control}>{control}</li>)}</ol>
        </div>
      </section>}
      {page.sections.map(([title, copy], index) => <section key={title}>
        <span>{String(index + 1).padStart(2, "0")}</span><div><h2>{title}</h2><p>{copy}</p>
          {pageKey === "product" && title === "Sovereign" && <Link className="text-link" to="/sovereign">Explore Sovereign <ArrowRight size={15} /></Link>}
        </div>
      </section>)}
      {pageKey === "developers" && <section aria-labelledby="developer-source-heading"><span>SRC</span><div>
        <h2 id="developer-source-heading">Review the implementation baseline</h2>
        <p>These source links pin the Phase 1 implementation baseline. Use the generated API reference for the exact deployed schemas; integration references may require a session or API credential.</p>
        <ul>{developerReferences.map(([label, path]) => <li key={path}><a className="text-link" href={`${baseline}${path}`}>{label} <ArrowRight size={15} /></a></li>)}</ul>
        <Link className="text-link" to="/docs">Read setup and result handling <ArrowRight size={15} /></Link>
        <p><a className="text-link" href="/api/docs">Open deployed API reference <ArrowRight size={15} /></a></p>
      </div></section>}
      {pageKey === "security" && <p><a className="text-link" href={`${baseline}SECURITY.md`}>Security disclosure policy <ArrowRight size={15} /></a></p>}
      <p><Link className="text-link" to={pageKey === "enterprise" ? "/contact" : pageKey === "security" ? "/trust" : "/docs"}>
        {pageKey === "enterprise" ? "Discuss an evaluation" : pageKey === "security" ? "Review the Trust Center" : "Get started with the docs"} <ArrowRight size={15} />
      </Link></p>
    </main>
    <PublicFooter />
  </div>;
}
