// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import type { customerAuthorityReader } from "../../lib/customerAuthorityReader";

type ReturnedAgents = Awaited<ReturnType<ReturnType<typeof customerAuthorityReader>["agents"]>>;
export type AgentInventoryReadState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "error" }
  | { status: "ready"; agents: ReturnedAgents };

// Preparation only. No production route imports this component. The caller must
// confirm that the inventory read contract is available; this is not a permit,
// an authority capability, a new backend capability schema, or a mutation API.
export function AgentInventoryPreparation({ state, readContractAvailable = false }: {
  state: AgentInventoryReadState;
  readContractAvailable?: boolean;
}) {
  return <section className="data-panel" aria-label="Agent inventory integration preparation">
    <header><div><h2>Agent inventory</h2><p>Integration preparation — not available in the customer console.</p></div></header>
    <p>Read-only backend-reported registration and delegation status. Neither registration nor a reported delegation authorizes an action. Every action still requires independent server authorization.</p>
    {!readContractAvailable || state.status === "unavailable" ? <p role="status">Agent inventory unavailable. A confirmed read contract is required; no registered agents or authority state are inferred.</p>
      : state.status === "loading" ? <p role="status">Loading backend-reported agent inventory…</p>
        : state.status === "error" ? <p role="alert">Agent inventory could not be confirmed. No empty or successful result is claimed.</p>
          : !state.agents.length ? <p role="status">No agent registrations were returned by this read. This is not proof that no agents or delegations exist elsewhere.</p>
            : <ul aria-label="Returned agent registrations">{state.agents.map((agent) => <li key={agent.id}>
              <article>
                <h3>{agent.displayName || "Unnamed agent registration"}</h3>
                <dl>
                  <div><dt>Agent ID</dt><dd><code style={{ overflowWrap: "anywhere", wordBreak: "break-word" }}>{agent.id}</code></dd></div>
                  <div><dt>Backend-reported lifecycle</dt><dd style={{ overflowWrap: "anywhere" }}>{agent.lifecycleState || "Not provided"}</dd></div>
                  <div><dt>Backend-reported delegation</dt><dd>{agent.reportedActiveDelegation ? "Reported active — not execution authority" : "No active delegation reported — no authority conclusion"}</dd></div>
                </dl>
                <p>Lifecycle labels are shown as returned. Unknown labels are not normalized to active, allowed, denied, or revoked.</p>
              </article>
            </li>)}</ul>}
    <section aria-label="Unavailable inventory integrations">
      <h3>Not available in this integration</h3>
      <ul><li>Application inventory: no integrated customer contract.</li><li>Policy bindings: no integrated customer contract.</li><li>Credential inventory: no integrated customer contract.</li><li>Delegation graph: no integrated customer contract. A delegation flag cannot reconstruct a graph or effective authority.</li></ul>
    </section>
  </section>;
}
