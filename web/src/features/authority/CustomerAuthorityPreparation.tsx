// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT

// Presentation states, NOT a proposed backend schema. This component is not
// imported by production navigation. It has no mutation API or authority logic.
export type AuthorityPreparationState =
  | { kind: "unavailable" }
  | { kind: "loading" }
  | { kind: "authentication-required" }
  | { kind: "forbidden" }
  | { kind: "expired" }
  | { kind: "unknown" }
  | { kind: "error" };

const messages: Record<AuthorityPreparationState["kind"], string> = {
  unavailable: "Unavailable: approved customer authority contracts are not integrated. No security operation can be submitted here.",
  loading: "Checking server-reported state. No completed operation is claimed.",
  "authentication-required": "Sign in again before inspecting the current operation. Do not repeat a change whose outcome is uncertain.",
  forbidden: "The operation is not available to this session. Owner privileges, step-up, and tenant access must be verified by the server.",
  expired: "The challenge or request has expired. Inspect current server state before beginning a new ceremony.",
  unknown: "Outcome uncertain. The response was not confirmed. Do not repeat the operation; inspect its authoritative status and evidence first.",
  error: "Current state could not be confirmed. No successful or empty result is claimed.",
};

export function CustomerAuthorityPreparation({ state = { kind: "unavailable" } }: { state?: AuthorityPreparationState }) {
  const alert = ["unknown", "error", "forbidden", "expired"].includes(state.kind);
  return <section className="data-panel" aria-label="Customer authority integration preparation">
    <header><div><h2>Customer authority setup</h2><p>Integration preparation — not available in the customer console.</p></div></header>
    <p>WhitePact — AI Agents. Actions Under Authority.</p>
    <p role={alert ? "alert" : "status"}>{messages[state.kind]}</p>
    <section aria-label="Passkeys and privileged authentication">
      <h3>Passkeys and privileged authentication</h3>
      <p>Organization signup establishes an account, not execution authority. A passkey response proves neither server verification nor permission to act.</p>
      <p>A reviewed server-issued challenge is required. Unsupported browsers, cancelled prompts, expired challenges, and revoked or lost credentials must not be treated as successful authentication.</p>
      <button type="button" disabled>Enroll passkey — awaiting approved integration</button>
      <p>If a passkey is lost, use the reviewed administrator recovery process when available. Never share a private key or recovery secret with support.</p>
    </section>
    <section aria-label="Root authority and explicit consent">
      <h3>Root authority and explicit consent</h3>
      <ol><li>Server verifies owner identity and eligibility.</li><li>Review the exact purpose, action types, targets, and scope.</li><li>Complete the required privileged authentication.</li><li>Explicitly confirm the exact operation.</li><li>Inspect server-confirmed status and evidence.</li></ol>
      <p>No consent has been recorded by viewing this page. Duplicate or lost responses require status reconciliation, not automatic resubmission. Root revocation status must come from the server.</p>
      <button type="button" disabled>Establish root — awaiting approved integration</button>
    </section>
    <section aria-label="Emergency containment">
      <h3>Emergency containment</h3>
      <p>Restrictive incident action is distinct from root recovery. Review the affected organization, agents, exact containment boundary, authentication requirement, and reason before confirmation.</p>
      <p>Pending or UNKNOWN is not contained. Only server verification of the documented boundary can confirm completion; unresolved executions require operator follow-up and incident evidence.</p>
      <button type="button" disabled>Contain — awaiting approved integration</button>
    </section>
    <section aria-label="Root recovery">
      <h3>Root recovery</h3>
      <p>Review the exact requested root change. Quorum requirements, distinct eligible administrator votes, conflicts, expiry, suspension, stale-request invalidation, and completion must be reported by the server.</p>
      <p>No vote count or recovery approval is calculated here. Re-authentication and reviewable audit history require approved contracts. Recovery does not silently expand consent.</p>
      <button type="button" disabled>Recover root — awaiting approved integration</button>
    </section>
  </section>;
}
