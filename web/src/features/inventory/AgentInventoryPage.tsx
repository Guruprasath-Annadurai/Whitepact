// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { Button } from "../../components/Button";
import { ApiError } from "../../lib/api";
import { customerAuthorityReader } from "../../lib/customerAuthorityReader";
import type { WebSession } from "../dashboard/DashboardShell";
import { AgentInventoryPreparation, type AgentInventoryReadState } from "./AgentInventoryPreparation";

export function AgentInventoryPage() {
  const session = useOutletContext<WebSession>();
  const organizationId = session.organization?.id;
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<{ organizationId: string; attempt: number; state: AgentInventoryReadState; failure?: string } | null>(null);
  const current = result && result.organizationId === organizationId && result.attempt === attempt ? result : null;
  useEffect(() => {
    if (!organizationId) return;
    const controller = new AbortController();
    let active = true;
    async function load() {
      try {
        const agents = await customerAuthorityReader({ organization: { id: organizationId! } }).agents(controller.signal);
        if (active) setResult({ organizationId: organizationId!, attempt, state: { status: "ready", agents } });
      } catch (cause) {
        if (!active) return;
        const failure = cause instanceof ApiError && cause.status === 401 ? "Your session has expired. Sign in again to read agent inventory."
          : cause instanceof ApiError && cause.status === 403 ? "The server did not permit this inventory read. Owner or admin membership is required."
            : "Agent inventory could not be confirmed. Retry this read when the service is available.";
        setResult({ organizationId: organizationId!, attempt, state: { status: "error" }, failure });
      }
    }
    void load();
    return () => { active = false; controller.abort(); };
  }, [organizationId, attempt]);
  return <main className="dashboard-content"><div className="page-heading"><div><h1>Agents</h1><p>Organization: {session.organization?.name ?? "Unavailable"}</p></div></div>
    <AgentInventoryPreparation key={`${organizationId ?? "unavailable"}:${attempt}`} state={!organizationId ? { status: "unavailable" } : current?.state ?? { status: "loading" }} readContractAvailable={Boolean(organizationId)} customerRead />
    {current?.failure && <p role="alert">{current.failure}</p>}
    {organizationId && current?.state.status === "error" && <Button onClick={() => setAttempt((value) => value + 1)}>Retry inventory read</Button>}
    <p>Registration, delegation, disablement and other privileged lifecycle changes are unavailable here.</p>
  </main>;
}
