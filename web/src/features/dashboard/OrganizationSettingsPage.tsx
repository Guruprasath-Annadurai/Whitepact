// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "../../components/Button";
import { ApiError, api } from "../../lib/api";
import type { WebSession } from "./DashboardShell";

type Organization = { id: string; name: string; slug: string; plan: string };
type Phase = "loading" | "ready" | "saving" | "uncertain" | "reconciling" | "error";
function object(value: unknown): value is Record<string, unknown> { return value !== null && typeof value === "object" && !Array.isArray(value); }
function validName(value: unknown): value is string { return typeof value === "string" && value.trim().length >= 2 && value.length <= 200; }
function organizationRead(value: unknown, id: string): Organization {
  if (!object(value) || value.source !== "organization_repository" || value.domain !== "organization" || !Array.isArray(value.items) || value.items.length !== 1) throw new Error("Unconfirmed organization response");
  const item: unknown = value.items[0];
  if (!object(item) || item.id !== id || !validName(item.name) || typeof item.slug !== "string" || typeof item.plan !== "string") throw new Error("Unconfirmed organization response");
  return { id, name: item.name, slug: item.slug, plan: item.plan };
}

// Rename preparation is testable only through this internal explicit contract
// seam. Production routes must leave it false until the backend can bind an
// expected organization/version atomically; a role or runtime flag is insufficient.
export function OrganizationSettingsPage({ session, renameContractVerified = false }: { session: WebSession; renameContractVerified?: boolean }) {
  const organizationId = session.organization?.id;
  const [phase, setPhase] = useState<Phase>("loading");
  const [record, setRecord] = useState<Organization | null>(null);
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const [notice, setNotice] = useState("");
  const active = useRef(false);
  const locked = useRef(true);
  const controller = useRef<AbortController | null>(null);
  const canRename = renameContractVerified && ["OWNER", "ADMIN"].includes(session.organization?.role ?? "");

  const inspect = useCallback(async (acknowledgedName?: string, unresolved = false) => {
    if (!organizationId) { setPhase("error"); setMessage("Authenticated organization context is unavailable."); return; }
    locked.current = true;
    setPhase(acknowledgedName !== undefined || unresolved ? "reconciling" : "loading");
    setMessage(""); setNotice("");
    controller.current?.abort();
    const request = new AbortController(); controller.current = request;
    try {
      const value = organizationRead(await api<unknown>("/api/v1/web/dashboard/organization", { signal: request.signal }), organizationId);
      if (!active.current || request.signal.aborted) return;
      setRecord(value); setName(value.name); setPhase("ready"); locked.current = false;
      if (acknowledgedName !== undefined) {
        if (value.name === acknowledgedName) setNotice("Organization name confirmed by the current server read.");
        else setMessage("The current server name differs from the submitted name. No rename success is claimed.");
      } else if (unresolved) setNotice("Current organization name reloaded. The earlier rename outcome was not confirmed.");
    } catch {
      if (!active.current || request.signal.aborted) return;
      setRecord(null);
      setPhase(acknowledgedName !== undefined || unresolved ? "uncertain" : "error");
      setMessage("The current organization name could not be confirmed. No empty or successful result is claimed.");
    }
  }, [organizationId]);

  useEffect(() => {
    active.current = true;
    void inspect();
    return () => { active.current = false; controller.current?.abort(); };
  }, [inspect]);

  async function save(event: FormEvent) {
    event.preventDefault();
    const submitted = name.trim();
    if (locked.current || !canRename || !organizationId || !record || !validName(submitted)) return;
    locked.current = true;
    setPhase("saving"); setMessage(""); setNotice("");
    try {
      const value = await api<unknown>("/api/v1/web/organization", { method: "PATCH", body: JSON.stringify({ name: submitted }) });
      if (!active.current) return;
      if (!object(value) || value.id !== organizationId || value.name !== submitted) throw new Error("Unconfirmed rename acknowledgement");
      await inspect(submitted);
    } catch (cause) {
      if (!active.current) return;
      if (cause instanceof ApiError && [400, 401, 403, 404, 409, 422, 429].includes(cause.status)) {
        const accessRefused = [401, 403, 404].includes(cause.status);
        locked.current = accessRefused; setPhase(accessRefused ? "error" : "ready");
        if (accessRefused) setRecord(null);
        setMessage(cause.status === 401 ? "Your session has expired. Sign in again before changing the organization name." : "The server rejected this name change. No successful rename is claimed.");
      } else {
        setPhase("uncertain");
        setMessage("The name change was not confirmed and may have completed. Check the current server name before submitting another change.");
      }
    }
  }

  const busy = ["loading", "saving", "reconciling"].includes(phase);
  return <main className="dashboard-content"><div className="page-heading"><div><h1>Organization</h1><p>Organization identity and name returned for the authenticated workspace.</p></div></div>
    <section className="data-panel settings-panel" aria-label="Organization settings" aria-busy={busy} style={{ overflowWrap: "anywhere" }}>
      {message && <p role="alert">{message}</p>}{notice && <p role="status">{notice}</p>}
      {busy ? <p role="status">{phase === "saving" ? "Submitting organization name change…" : phase === "reconciling" ? "Checking the current server name…" : "Loading organization…"}</p>
        : phase === "uncertain" ? <><p>Another rename is disabled until a current read succeeds. The submitted name is not presented as persisted.</p><Button onClick={() => void inspect(undefined, true)}>Check current organization name</Button></>
          : phase === "error" ? <Button onClick={() => void inspect()}>Retry organization read</Button>
            : record && (!renameContractVerified ? <><h2>Organization name</h2><p>{record.name}</p><OrganizationMetadata record={record} user={session.user.full_name} /><p>Organization name changes are unavailable pending workspace confirmation.</p></> : <form onSubmit={save} aria-label="Organization name"><label className="field"><span>Organization name</span><input value={name} onChange={(event) => setName(event.target.value)} required minLength={2} maxLength={200} readOnly={!canRename} /></label>
              <OrganizationMetadata record={record} user={session.user.full_name} />
              {canRename ? <Button disabled={!validName(name.trim()) || name.trim() === record.name}>Save organization</Button> : <p>Name changes require owner or admin membership and independent server authorization.</p>}
            </form>)}
    </section>
  </main>;
}

function OrganizationMetadata({ record, user }: { record: Organization; user: string }) {
  return <div className="metadata-grid"><p><span>Organization ID</span><code style={{ overflowWrap: "anywhere" }}>{record.id}</code></p><p><span>Slug</span><strong>{record.slug}</strong></p><p><span>Signed-in user</span><strong>{user}</strong></p><p><span>Plan</span><strong>{record.plan}</strong></p></div>;
}
