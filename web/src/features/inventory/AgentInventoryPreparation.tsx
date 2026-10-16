// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import type { customerAuthorityReader } from "../../lib/customerAuthorityReader";
import { useState } from "react";

type ReturnedAgents = Awaited<ReturnType<ReturnType<typeof customerAuthorityReader>["agents"]>>;
export type AgentInventoryReadState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "error" }
  | { status: "ready"; agents: ReturnedAgents };

// The caller must confirm that the inventory read contract is available. The
// default presentation remains preparation only; this is not a permit,
// an authority capability, a new backend capability schema, or a mutation API.
export function AgentInventoryPreparation({ state, readContractAvailable = false, customerRead = false, errorMessage }: {
  state: AgentInventoryReadState;
  readContractAvailable?: boolean;
  customerRead?: boolean;
  errorMessage?: string;
}) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const canRead = readContractAvailable && state.status === "ready";
  const agents = canRead ? state.agents : [];
  const filtered = agents.filter((agent) => [agent.id, agent.displayName, agent.lifecycleState].some((value) => value.toLowerCase().includes(query.trim().toLowerCase())));
  const pageCount = Math.max(1, Math.ceil(filtered.length / 10));
  const currentPage = Math.min(page, pageCount - 1);
  const visible = filtered.slice(currentPage * 10, (currentPage + 1) * 10);
  return <section className="data-panel" aria-label={customerRead ? "Read-only agent inventory" : "Agent inventory integration preparation"} aria-busy={readContractAvailable && state.status === "loading"}>
    <header><div><h2>Agent inventory</h2><p>{customerRead ? "Registered agents returned for the authenticated organization. Read-only access requires an owner or admin membership." : "Integration preparation — not available in the customer console."}</p></div></header>
    <p>Read-only backend-reported registration and delegation status. Neither registration nor a reported delegation authorizes an action. Every action still requires independent server authorization.</p>
    {!readContractAvailable || state.status === "unavailable" ? <p role="status">Agent inventory unavailable. A confirmed read contract is required; no registered agents or authority state are inferred.</p>
      : state.status === "loading" ? <p role="status">Loading backend-reported agent inventory…</p>
        : state.status === "error" ? <p role="alert">{errorMessage && <span>{errorMessage} </span>}Agent inventory could not be confirmed. No empty or successful result is claimed.</p>
          : !state.agents.length ? <p role="status">No agent registrations were returned by this read. This is not proof that no agents or delegations exist elsewhere.</p>
            : <>
              <label className="field"><span>Filter loaded agent registrations</span><input type="search" value={query} onChange={(event) => { setQuery(event.target.value); setPage(0); }} /></label>
              <p>Filtering and pages apply only to the returned registrations. The backend read has no pagination or total-count contract; this view does not establish a complete inventory.</p>
              <p aria-live="polite">{filtered.length ? `Showing ${currentPage * 10 + 1}–${Math.min((currentPage + 1) * 10, filtered.length)} of ${filtered.length} matching loaded registrations.` : "No loaded agent registrations match this filter."}</p>
              <ul aria-label="Returned agent registrations">{visible.map((agent) => <li key={agent.id}>
              <article>
                <h3>{agent.displayName || "Unnamed agent registration"}</h3>
                <dl>
                  <div><dt>Agent ID</dt><dd><code style={{ overflowWrap: "anywhere", wordBreak: "break-word" }}>{agent.id}</code></dd></div>
                  <div><dt>Backend-reported lifecycle</dt><dd style={{ overflowWrap: "anywhere" }}>{agent.lifecycleState || "Not provided"}</dd></div>
                  <div><dt>Backend-reported delegation</dt><dd>{agent.reportedActiveDelegation ? "Reported active — not execution authority" : "No active delegation reported — no authority conclusion"}</dd></div>
                  <div><dt>Application ownership</dt><dd>Unavailable — no integrated customer ownership contract.</dd></div>
                  <div><dt>Capabilities</dt><dd>Unavailable — registration and delegation status do not describe executable capabilities.</dd></div>
                </dl>
                <p>Lifecycle labels are shown as returned. Unknown labels are not normalized to active, allowed, denied, or revoked.</p>
              </article>
            </li>)}</ul>
              {filtered.length > 10 && <nav aria-label="Loaded agent registration pages"><button type="button" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>Previous loaded page</button><span>Page {currentPage + 1} of {pageCount}</span><button type="button" disabled={currentPage + 1 >= pageCount} onClick={() => setPage(currentPage + 1)}>Next loaded page</button></nav>}
            </>}
    <section aria-label="Unavailable inventory integrations">
      <h3>Not available in this integration</h3>
      <ul><li>Application inventory: no integrated customer contract.</li><li>Policy bindings: no integrated customer contract.</li><li>Credential inventory: no integrated customer contract.</li><li>Delegation graph: no integrated customer contract. A delegation flag cannot reconstruct a graph or effective authority.</li></ul>
    </section>
  </section>;
}
