// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { Button } from "../../components/Button";
import { ApiError } from "../../lib/api";
import { customerAuthorityReader } from "../../lib/customerAuthorityReader";
import type { WebSession } from "../dashboard/DashboardShell";

type ReportedStatus = Awaited<ReturnType<ReturnType<typeof customerAuthorityReader>["status"]>>;
type Result = { organizationId: string; attempt: number } & (
  | { kind: "ready"; value: ReportedStatus }
  | { kind: "error"; message: string; signIn: boolean }
);

export function AuthorityRecordStatus() {
  const session = useOutletContext<WebSession>();
  const organizationId = session.organization?.id;
  const [attempt, setAttempt] = useState(-1);
  const [result, setResult] = useState<Result | null>(null);
  const current = result && result.organizationId === organizationId && result.attempt === attempt ? result : null;

  useEffect(() => {
    if (!organizationId || attempt < 0) return;
    const id = organizationId;
    const controller = new AbortController();
    let active = true;
    async function load() {
      try {
        const value = await customerAuthorityReader({ organization: { id } }).status(controller.signal);
        if (active) setResult({ organizationId: id, attempt, kind: "ready", value });
      } catch (cause) {
        if (!active) return;
        const signIn = cause instanceof ApiError && cause.status === 401;
        const message = signIn ? "Your session has expired. Sign in again to inspect the reported status."
          : cause instanceof ApiError && cause.status === 403 ? "This session cannot read the reported status. Owner or admin membership is required."
            : "The reported status could not be confirmed. No inactive or successful state is inferred. Retry this read when the service is available.";
        setResult({ organizationId: id, attempt, kind: "error", message, signIn });
      }
    }
    void load();
    return () => { active = false; controller.abort(); };
  }, [organizationId, attempt]);

  return <section className="data-panel" aria-label="Reported root and consent records" aria-busy={Boolean(organizationId && attempt >= 0 && !current)}>
      <h2>Backend-reported record state</h2>
      <p>This read reports root and consent records. It does not evaluate effective capabilities, prove current execution permission, or authorize an action. Each action requires independent server authorization.</p>
      {!organizationId ? <p>Authenticated organization context is unavailable. No status read was submitted.</p>
        : attempt < 0 ? <p>No record-status read has been requested.</p>
          : !current ? <p role="status">Loading reported root and consent record state…</p>
          : current.kind === "error" ? <div role="alert"><p>{current.message}</p>{current.signIn && <a href="/login?next=%2Fdashboard%2Fagents">Sign in again</a>}</div>
            : <><p role="status">{current.value.reportedActive ? "The backend reports an unrevoked root and consent record pair. This is not execution authority." : "The backend did not report an active root and consent record pair. No specific expiry or revocation reason is inferred."}</p>
              <dl className="metadata-grid">
                <div><dt>Reported root record ID</dt><dd><code style={{ overflowWrap: "anywhere" }}>{current.value.rootId ?? "Not returned"}</code></dd></div>
                <div><dt>Reported consent record ID</dt><dd><code style={{ overflowWrap: "anywhere" }}>{current.value.consentId ?? "Not returned"}</code></dd></div>
                <div><dt>Reported revocation epoch</dt><dd>{current.value.epoch}</dd></div>
              </dl>
              <p>This is a read snapshot. A displayed record ID or epoch is not a live revocation guarantee.</p>
            </>}
      {organizationId && <Button variant="secondary" disabled={attempt >= 0 && !current} onClick={() => setAttempt((value) => value + 1)}>{attempt < 0 ? "Read reported root and consent status" : current?.kind === "error" ? "Retry status read" : "Refresh reported status"}</Button>}
      <p>Passkey enrollment, root establishment, consent changes, delegation, containment, recovery and revocation are not enabled by this panel. Application ownership and executable capability inventory remain unavailable.</p>
  </section>;
}
