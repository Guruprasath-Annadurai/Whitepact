// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import type { RecoveryRecord } from "./recoveryReader";

export type RecoveryReadState = { kind: "unavailable" } | { kind: "loading" } | { kind: "error" } | { kind: "ready"; records: RecoveryRecord[] };
export function RecoveryRecordsPreparation({ state }: { state: RecoveryReadState }) {
  return <section className="data-panel" aria-label="Recovery records integration preparation">
    <h2>Server-reported recovery records</h2>
    <p>Read-only integration preparation. Reported status is not proof of an eligible quorum, approved recovery, or execution authority.</p>
    {state.kind === "unavailable" ? <p role="status">Recovery records unavailable. No successful or empty result is inferred.</p>
      : state.kind === "loading" ? <p role="status">Loading recovery records…</p>
        : state.kind === "error" ? <p role="alert">Recovery records could not be confirmed. No recovery result is claimed.</p>
          : state.records.length === 0 ? <p role="status">No records were returned by this read. No recovery or authority conclusion is implied.</p>
            : <ul>{state.records.map((record) => <li key={record.id} style={{ overflowWrap: "anywhere" }}>
              <h3>{record.type || "Unspecified request type"}</h3>
              <dl><dt>Request ID</dt><dd>{record.id}</dd><dt>Target root</dt><dd>{record.rootId}</dd>
                <dt>Requester</dt><dd>{record.requesterId}</dd><dt>Reported status</dt><dd>{record.status || "Not provided"}</dd>
                <dt>Server-reported expiry</dt><dd>{record.expiresAt || "Not provided"}</dd></dl>
            </li>)}</ul>}
    <p>Voting, execution and authoritative quorum progress are unavailable pending the corrected security contract. No vote tally is computed here.</p>
  </section>;
}
