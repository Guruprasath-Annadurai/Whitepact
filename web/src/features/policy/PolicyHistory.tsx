// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { useRef, useState } from "react";
import { Button } from "../../components/Button";
import { api } from "../../lib/api";
import "./PolicyHistory.css";

type Entry = { version: number; change: string; actor_type: string; actor_id: string; created_at: string; entry_digest: string; rule_id: string | null };
type History = { chain_valid: boolean; checkpoint_checked: boolean; head: { version: number; entry_digest: string } | null; entries: Entry[] };

function historyPayload(value: unknown): value is History {
  if (!value || typeof value !== "object") return false;
  const result = value as History;
  return typeof result.chain_valid === "boolean" && typeof result.checkpoint_checked === "boolean" && (result.head === null || (!!result.head && Number.isInteger(result.head.version) && typeof result.head.entry_digest === "string")) && Array.isArray(result.entries) && result.entries.every((entry) => entry && Number.isInteger(entry.version) && typeof entry.change === "string" && typeof entry.actor_type === "string" && typeof entry.actor_id === "string" && typeof entry.created_at === "string" && typeof entry.entry_digest === "string");
}

export function PolicyHistory() {
  const [state, setState] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [history, setHistory] = useState<History | null>(null);
  const busy = useRef(false);
  async function load() {
    if (busy.current) return;
    busy.current = true; setState("loading"); setHistory(null);
    try {
      const value = await api<unknown>("/api/v1/web/policy/history?limit=100");
      if (!historyPayload(value)) throw new Error("Malformed history");
      setHistory(value); setState("success");
    } catch { setState("error"); }
    finally { busy.current = false; }
  }
  return <section className="data-panel policy-history"><h2>Policy version history</h2><p>Up to 100 returned changes. This is not complete history or independent checkpoint verification. Server permissions apply.</p><Button variant="secondary" disabled={state === "loading"} onClick={() => void load()}>{state === "loading" ? "Loading history…" : "Load policy history"}</Button>
    {state === "loading" && <p role="status">Reading canonical policy history…</p>}
    {state === "error" && <p role="alert">Policy history is unavailable or was not permitted. No valid history is claimed. Retry the read when access and service availability are confirmed.</p>}
    {history && <><p role="status">{history.chain_valid ? "Backend reports chain valid" : "Backend reports chain invalid"}. {history.checkpoint_checked ? "Backend checked a supplied checkpoint." : "No external checkpoint was checked."}</p>{history.head && <dl><div><dt>Recorded head version</dt><dd>{history.head.version}</dd></div><div><dt>Recorded head digest</dt><dd><code>{history.head.entry_digest}</code></dd></div></dl>}{history.entries.length ? <div className="evidence-cards">{history.entries.map((entry) => <article key={entry.version}><h3>Version {entry.version}: {entry.change}</h3><dl><div><dt>Actor</dt><dd>{entry.actor_type}: {entry.actor_id}</dd></div><div><dt>Rule</dt><dd>{entry.rule_id ?? "Ordered policy"}</dd></div><div><dt>Recorded at</dt><dd>{entry.created_at}</dd></div><div><dt>Entry digest</dt><dd><code>{entry.entry_digest}</code></dd></div></dl></article>)}</div> : <p>No recorded policy changes returned.</p>}</>}
  </section>;
}
