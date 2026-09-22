// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { useEffect, useState } from "react";
import { Binary, Braces, ChevronLeft, CircleHelp, Clock3, Eye, FileCheck2, FlaskConical, GitCompareArrows, ListTree, Menu, Network, PackageCheck, PanelRightClose, Radar, Route, ScanSearch, Search, ShieldCheck, X, ZoomIn, ZoomOut } from "lucide-react";
import { Link } from "react-router-dom";
import type { SovereignCapabilities } from "../../../../sdk/typescript/sovereign/types";
import { Brand } from "../../components/Brand";
import { Seo } from "../../components/Seo";
import { browserCapabilityState, sovereignFixturesAllowed, sovereignOperations, sovereignWebApi, type SovereignFeatureName, type SovereignOperation, type SovereignPayload } from "./SovereignApi";

const tools = [
  ["Authority Lens", Network, "xray"], ["Expected vs Effective", GitCompareArrows, "authority_compare"], ["Debugger", ScanSearch, "explain"], ["Trace", Route, "trace"], ["Blast Radius", Radar, "simulate_blast_radius"], ["Mission Simulator", Binary, "simulate_mission"], ["Shadow Mode", Eye, "shadow"], ["Policy Lab", FlaskConical, "policy_lab"], ["Gauntlet", ShieldCheck, "gauntlet"], ["Flight Recorder", FileCheck2, "flight_recorder"], ["Time Machine", Clock3, "time_machine"], ["Evidence Explorer", Braces, "evidence"], ["Capsules", PackageCheck, "capsule"], ["Authority BOM", ListTree, "authority_bom"],
] as const;
const nodes = ["Identity", "Authority", "Policy", "Risk", "Approval", "Decision", "Evidence"];
const liveTools: Record<string, { operation: SovereignOperation; payload: SovereignPayload; label: string; note?: string }> = {
  "Authority Lens": { operation: "xray", payload: {}, label: "Load authority graph" },
  "Expected vs Effective": { operation: "compare", payload: { manifest: {} }, label: "Compare declared expectation", note: "Manifest input is a DECLARED EXPECTATION. Effective authority is evaluated by Sovereign Core." },
  Debugger: { operation: "explain", payload: { evidence_id: "" }, label: "Explain evidence" },
  Trace: { operation: "trace", payload: { evidence_id: "" }, label: "Trace evidence" },
  "Blast Radius": { operation: "blastRadius", payload: { actor_identity_id: "", hypothetical_extra_capabilities: [] }, label: "Run projected simulation", note: "Zero-effect projection. No external action is executed." },
  "Mission Simulator": { operation: "mission", payload: { agent_id: "", steps: [] }, label: "Run mission simulation", note: "Zero-effect simulation. UNKNOWN outcomes remain UNKNOWN." },
  "Shadow Mode": { operation: "shadow", payload: { agent_id: "", action_type: "", target: "shadow:target", persist: false }, label: "Evaluate shadow observation", note: "Observed evaluation only; this does not execute the action." },
  "Policy Lab": { operation: "policyLint", payload: { rules: [] }, label: "Lint policy", note: "Zero-effect policy analysis. Validation uses the canonical lint alias." },
  Gauntlet: { operation: "gauntlet", payload: {}, label: "Run canonical probes", note: "PASS is shown only when returned by the backend." },
  "Flight Recorder": { operation: "flightRecorder", payload: { evidence_id: "" }, label: "Reconstruct flight record", note: "Reconstructed from canonical evidence; no effect is replayed." },
  "Time Machine": { operation: "timeMachine", payload: {}, label: "Reconstruct comparison", note: "Historical provenance may be partial. Results are not represented as exact policy-at-T truth." },
  "Evidence Explorer": { operation: "evidence", payload: { evidence_id: "" }, label: "Correlate evidence", note: "Correlation identifiers do not independently prove an external side effect." },
  Capsules: { operation: "capsuleCreate", payload: { authority_subset: {}, timeline: [] }, label: "Create capsule", note: "Create, validate, or reproduce through canonical zero-effect routes; V1 has no separate inspect endpoint." },
  "Authority BOM": { operation: "authorityBom", payload: {}, label: "Load experimental Authority BOM", note: "Experimental output may be incomplete." },
};

export function SovereignWorkbench() {
  const [active, setActive] = useState("Authority Lens");
  const [selected, setSelected] = useState("Authority");
  const [tab, setTab] = useState("Overview");
  const [notice, setNotice] = useState(true);
  const [sidebar, setSidebar] = useState(false);
  const [capabilities, setCapabilities] = useState<SovereignCapabilities | null>(null);
  const [coreVersion, setCoreVersion] = useState<string | null>(null);
  const [negotiation, setNegotiation] = useState<"loading" | "ready" | "error">("loading");
  const [mode, setMode] = useState<"live" | "fixture">("live");
  const fixtureAllowed = sovereignFixturesAllowed(import.meta.env.DEV);
  const feature = tools.find(([name]) => name === active)?.[2] as SovereignFeatureName;
  const browserState = browserCapabilityState(capabilities, feature);
  const showFixture = fixtureAllowed && mode === "fixture" && active === "Authority Lens";
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
    <main className="sov-workbench__main"><header><div><h1>{active}</h1><p>{active === "Authority Lens" ? "Inspect configured authority relationships and supporting evidence." : "Capability state is negotiated from Sovereign Core."}</p></div><div className="mode-switch" aria-label="Data mode"><button aria-pressed={showFixture} disabled={!fixtureAllowed || active !== "Authority Lens"} onClick={() => setMode("fixture")}>Development preview</button><button aria-pressed={!showFixture} disabled={browserState !== "AVAILABLE" && browserState !== "EXPERIMENTAL"} onClick={() => setMode("live")}>Production</button><span>{negotiation === "loading" ? "Negotiating" : browserState === "EXPERIMENTAL" ? "Experimental" : browserState === "AVAILABLE" ? "Available" : "Unavailable"}</span></div></header>
      {showFixture && notice && <section className="fixture-notice" role="status"><CircleHelp /><div><strong>Development fixture — not production authority data</strong><p>This environment contains fixture data for UI and integration development. No production authority result is displayed.</p></div><button onClick={() => setNotice(false)}>Dismiss <X /></button></section>}
      {negotiation === "loading" && !showFixture ? <NegotiationState title="Negotiating Sovereign capabilities" copy="Reading canonical status and capability descriptors." /> : negotiation === "error" && !showFixture ? <NegotiationState title="Sovereign negotiation unavailable" copy="The browser could not read the canonical capability endpoint. No authority data is shown." /> : showFixture ? <AuthorityWorkspace selected={selected} onSelect={setSelected} /> : browserState === "AVAILABLE" || browserState === "EXPERIMENTAL" ? <LiveTool key={active} title={active} /> : <UnavailableTool title={active} state={browserState} />}
    </main>
    {showFixture ? <Inspector selected={selected} tab={tab} onTab={setTab} /> : <aside aria-label="Sovereign capability status" className="sov-inspector sov-inspector--capability"><div className="inspector-empty"><PanelRightClose /><h2>Canonical browser boundary</h2><p>Tenant context is derived from the authenticated session. Browser requests never provide organization identity.</p><strong>{browserState}</strong></div></aside>}
    <footer aria-label="Sovereign connection status" className="sov-workbench__status" tabIndex={0}><strong>Core negotiation: {negotiation}</strong><span>Sovereign Core: {coreVersion ?? "unknown"}</span><span>{showFixture ? "Development fixture · No live authority" : "Production fixture usage: none"}</span></footer>
  </div>;
}

function AuthorityWorkspace({ selected, onSelect }: { selected: string; onSelect: (value: string) => void }) { return <div className="authority-workspace"><div className="authority-toolbar"><label><Search /><span className="sr-only">Search fixture nodes</span><input placeholder="Search fixture nodes…" /></label><span>Fixture preview</span></div><section className="authority-canvas" aria-label="Fixture authority relationship graph"><div className="zoom-controls"><button aria-label="Zoom in"><ZoomIn /></button><button aria-label="Zoom out"><ZoomOut /></button></div><div className="authority-nodes">{nodes.map((node, index) => <button className={selected === node ? "selected" : ""} key={node} onClick={() => onSelect(node)}><span>{index + 1}</span><strong>{node}</strong><code>{node.toLowerCase()}_fixture_01</code></button>)}</div><div className="fixture-constraint"><ShieldCheck /><strong>Constraint</strong><code>con_fixture_01</code></div></section><section aria-label="Configured fixture trace" className="trace-rail" tabIndex={0}><header><strong>Trace · configured path</strong><span>Fixture values only</span></header><ol>{nodes.map((node, index) => <li className={selected === node ? "active" : ""} key={node}><span>{index + 1}</span><strong>{node}</strong><code>{node.toLowerCase()}_fixture_01</code></li>)}</ol></section></div>; }

function Inspector({ selected, tab, onTab }: { selected: string; tab: string; onTab: (tab: string) => void }) { const tabs = ["Overview", "Relationships", "Configured rules", "Evidence"]; return <aside className="sov-inspector"><header><div><Network /><span><strong>{selected.toLowerCase()}_fixture_01</strong><small>{selected}</small></span></div><span>Development fixture</span></header><div className="inspector-tabs" role="tablist" aria-label="Node inspector sections">{tabs.map((name) => <button role="tab" aria-selected={tab === name} onClick={() => onTab(name)} key={name}>{name}</button>)}</div>{tab === "Overview" ? <div className="inspector-content"><section><h2>Node details</h2><dl><div><dt>Node ID</dt><dd><code>{selected.toLowerCase()}_fixture_01</code></dd></div><div><dt>Type</dt><dd>{selected}</dd></div><div><dt>Source</dt><dd>Development fixture</dd></div></dl></section><section><h2>Expected relationship</h2><p>Configured fixture relationship available for interface development.</p></section><section><h2>Effective relationship</h2><p>Effective relationships are computed by Sovereign Core and are not available in this fixture.</p><strong className="contract-wait"><PanelRightClose /> Tenant-bound web contract required</strong></section></div> : <div className="inspector-empty"><Braces /><h2>{tab}</h2><p>This fixture panel never represents canonical production data.</p></div>}</aside>; }

function UnavailableTool({ title, state }: { title: string; state: string }) { return <section className="sov-tool-unavailable"><PanelRightClose /><h2>{title} is unavailable in this browser session</h2><p>Canonical capability negotiation does not make this result available. No result is calculated or fabricated in React.</p><strong>{state === "UNKNOWN" ? "CAPABILITY STATUS UNKNOWN" : "FEATURE UNAVAILABLE"}</strong></section>; }
function NegotiationState({ title, copy }: { title: string; copy: string }) { return <section className="sov-tool-unavailable" role="status"><CircleHelp /><h2>{title}</h2><p>{copy}</p></section>; }
const groupedOperations: Partial<Record<string, SovereignOperation[]>> = {
  "Expected vs Effective": ["effective", "compare", "drift"],
  "Policy Lab": ["policyLint", "policyValidate", "policyTest", "policyDiff", "policySimulate"],
  Capsules: ["capsuleCreate", "capsuleValidate", "capsuleReproduce"],
};
const operationLabels: Partial<Record<SovereignOperation, string>> = {
  effective: "Effective authority", compare: "Compare", drift: "Drift",
  policyLint: "Lint", policyValidate: "Validate", policyTest: "Test", policyDiff: "Diff", policySimulate: "Simulate",
  capsuleCreate: "Create", capsuleValidate: "Validate", capsuleReproduce: "Reproduce",
};

function payloadFor(operation: SovereignOperation, fallback: SovereignPayload): SovereignPayload {
  if (operation === "effective") return {};
  if (operation === "drift" || operation === "compare") return { manifest: {} };
  if (operation === "policyTest") return { cases: [] };
  if (["policyLint", "policyValidate", "policyDiff"].includes(operation)) return { rules: [] };
  if (operation === "policySimulate") return { rules: [], action_types: [] };
  if (["capsuleValidate", "capsuleReproduce"].includes(operation)) return { capsule: {} };
  if (operation === "capsuleCreate") return { authority_subset: {}, timeline: [] };
  return fallback;
}

function LiveTool({ title }: { title: string }) {
  const definition = liveTools[title];
  const choices = groupedOperations[title] ?? [definition.operation];
  const [operation, setOperation] = useState<SovereignOperation>(definition.operation);
  const [source, setSource] = useState(() => JSON.stringify(definition.payload, null, 2));
  const [result, setResult] = useState<SovereignPayload | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  function selectOperation(next: SovereignOperation) { setOperation(next); setSource(JSON.stringify(payloadFor(next, definition.payload), null, 2)); setResult(null); setState("idle"); }
  async function execute() {
    setState("loading"); setMessage(""); setResult(null);
    try {
      const response = await sovereignWebApi.execute(operation, JSON.parse(source) as SovereignPayload);
      setResult(response); setState("success");
    } catch (error) {
      const classified = sovereignWebApi.classify(error);
      const messages: Record<string, string> = {
        INVALID_REQUEST: "The request is invalid. Organization identity cannot be supplied by the browser.",
        UNAUTHENTICATED: "Authentication is required. Sign in again to continue.",
        CSRF_REJECTED: "The session security token is missing or expired. Refresh and try again.",
        NOT_FOUND: "The requested resource does not exist or is not available to this organization.",
        ORGANIZATION_UNAVAILABLE: "No organization membership is available for this session.",
        FEATURE_UNAVAILABLE: "This Sovereign capability is unavailable on the current deployment.",
        NETWORK: error instanceof SyntaxError ? "Request input must be valid JSON." : "Sovereign Core could not be reached.",
        BACKEND: "Sovereign Core returned an error. No result was inferred.",
      };
      setMessage(messages[classified.kind]); setState("error");
    }
  }
  return <section className="sov-live-tool" aria-labelledby="sov-live-title">
    <header><div><span>{"experimental" in sovereignOperations[operation] ? "EXPERIMENTAL" : "LIVE"}</span><h2 id="sov-live-title">{title}</h2></div><strong>Tenant derived from session</strong></header>
    {choices.length > 1 && <div className="sov-operation-tabs" role="tablist" aria-label={`${title} operations`}>{choices.map((choice) => <button role="tab" aria-selected={operation === choice} key={choice} onClick={() => selectOperation(choice)}>{operationLabels[choice] ?? choice}</button>)}</div>}
    {definition.note && <p className="sov-live-note">{definition.note}</p>}
    <label className="sov-json-input"><span>Canonical request input</span><textarea spellCheck={false} value={source} onChange={(event) => setSource(event.target.value)} aria-describedby="sov-input-help" /></label>
    <p id="sov-input-help" className="sov-input-help">Do not include organization or tenant identifiers. The server derives organization context from the authenticated session.</p>
    <div className="sov-live-actions"><button className="wp-button wp-button--primary" disabled={state === "loading"} onClick={execute}>{state === "loading" ? "Running…" : operationLabels[operation] ?? definition.label}</button>{title === "Evidence Explorer" && <Link className="wp-button wp-button--secondary" to="/dashboard/evidence">Open Evidence console</Link>}</div>
    {state === "error" && <div className="sov-live-error" role="alert"><CircleHelp /><strong>Result unavailable</strong><p>{message}</p></div>}
    {state === "success" && result && <div className="sov-live-result" role="status" aria-live="polite"><header><strong>Canonical backend result</strong><span>No frontend disposition inferred</span></header><pre>{JSON.stringify(result, null, 2)}</pre></div>}
  </section>;
}
