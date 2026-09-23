// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { FormEvent, useState } from "react";
import { Search } from "lucide-react";
import { api, messageFrom } from "../../lib/api";
import { Button } from "../../components/Button";

type Resolution = {
  status: string;
  confidence: number;
  message?: string;
  entity?: {
    entity_id: string;
    canonical_name: string;
    entity_type: string;
    confidence: number;
    evidence_state: string;
    last_verified_at?: string;
  };
  candidates?: Array<{ entity: { entity_id: string; canonical_name: string }; confidence: number }>;
};

type Profile = {
  entity: Resolution["entity"];
  summary: string;
  claims: Array<{ claim_id: string; predicate: string; normalized_value?: string; evidence_state: string }>;
  relationships: Array<{ predicate: string; object_entity_id: string; evidence_state: string }>;
  conflicts: unknown[];
  sources: Array<{ canonical_url: string; quality_tier: string }>;
};

export function GlobalDirectoryPage() {
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [resolution, setResolution] = useState<Resolution | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSearch(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setProfile(null);
    try {
      const res = await api<Resolution>(`/api/v1/global-directory/resolve?q=${encodeURIComponent(query)}`);
      setResolution(res);
      if (res.entity?.entity_id) {
        const detail = await api<Profile>(`/api/v1/global-directory/entities/${res.entity.entity_id}`);
        setProfile(detail);
      }
    } catch (cause) {
      setError(messageFrom(cause, "Global Directory search failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="dashboard-content">
      <div className="page-heading">
        <div>
          <h1>Global Directory</h1>
          <p>Provenance-aware entity resolution. Knowledge is not execution authority.</p>
        </div>
      </div>
      {error && <div className="form-error" role="alert">{error}</div>}
      <section className="data-panel settings-panel">
        <form onSubmit={onSearch}>
          <label className="field">
            <span>Resolve entity</span>
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Person, organization, repository URL…" required />
          </label>
          <Button disabled={busy}><Search aria-hidden="true" /> {busy ? "Resolving…" : "Search"}</Button>
        </form>
      </section>
      {resolution?.status === "ambiguous" && (
        <section className="data-panel">
          <h2>Ambiguous identity</h2>
          <p>{resolution.message}</p>
          <ul>
            {resolution.candidates?.map((c) => (
              <li key={c.entity.entity_id}>{c.entity.canonical_name} ({c.confidence.toFixed(2)})</li>
            ))}
          </ul>
        </section>
      )}
      {profile?.entity && (
        <section className="data-panel">
          <header>
            <h2>{profile.entity.canonical_name}</h2>
            <p>{profile.entity.entity_type} · confidence {profile.entity.confidence.toFixed(2)} · {profile.entity.evidence_state}</p>
          </header>
          <p className="configuration-note">{profile.summary}</p>
          <h3>Relationships</h3>
          <ul>
            {profile.relationships.map((r) => (
              <li key={`${r.predicate}-${r.object_entity_id}`}>{r.predicate} → {r.object_entity_id} ({r.evidence_state})</li>
            ))}
          </ul>
          <h3>Claims</h3>
          <ul>
            {profile.claims.map((c) => (
              <li key={c.claim_id}>{c.predicate} {c.normalized_value ?? ""} — {c.evidence_state}</li>
            ))}
          </ul>
          <h3>Sources</h3>
          <ul>
            {profile.sources.map((s) => (
              <li key={s.canonical_url}><a href={s.canonical_url} rel="noreferrer">{s.canonical_url}</a> ({s.quality_tier})</li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
