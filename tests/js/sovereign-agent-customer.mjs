// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
// Actual development agent process. It never sends the human browser cookies.
import assert from "node:assert/strict";
import { generateKeyPairSync, sign } from "node:crypto";

const audience = "whitepact:dev-agent-intent:v1";
const intentPath = "/api/dev/agent-auth/intent";

export async function runDevelopmentAgent({ origin, call, expect, mark, setPhase, agent, authority, consent, requests }) {
  const keys = generateKeyPairSync("ed25519");
  const publicKey = keys.publicKey.export({ format: "der", type: "spki" }).subarray(-32).toString("hex");
  const signed = challenge => sign(null, Buffer.from(challenge.message, "base64url"), keys.privateKey).toString("base64url");
  const auth = authority.replace(/\/authority$/, "/agent-auth");
  let phase = "judgment";
  const set = value => { phase = value; setPhase(value); };
  set(phase);
  const reusable = await call("/api/web/api-keys", "POST", { name: "Must remain identity gated", environment: "test", scopes: ["governance:read"] });
  assert.equal(reusable.status, 403);
  const issueChallenge = expect(await call(`${auth}/challenge`, "POST", { agent_id: agent.agent_id, public_key: publicKey }), 200);
  const issued = expect(await call(`${auth}/issue`, "POST", { challenge_id: issueChallenge.challenge_id, signature: signed(issueChallenge) }), 200);
  assert.equal(issued.authentication_only, true);
  assert.equal(issued.development_only, true);
  assert.equal(issued.audience, audience);
  const intent = { name: "rai_policy_check", arguments: { text: "Harmless local development evaluation", policy: { blocked_topics: ["prohibited-content"] } }, purpose: consent.purpose };
  const agentCall = async (path, body) => {
    const response = await fetch(new URL(path, origin), {
      method: "POST", signal: AbortSignal.timeout(30000),
      headers: { "Content-Type": "application/json", Authorization: `B1-PoP ${issued.credential}` },
      body: JSON.stringify(body),
    });
    let value = null;
    try { value = await response.json(); } catch { /* Invalid response is never success. */ }
    requests.push({ phase, path, method: "POST", http_status: response.status, authentication: "agent_pop", human_cookie_sent: false });
    return { status: response.status, value };
  };
  const challenge = expect(await agentCall("/api/dev/agent-auth/request-challenge", { audience, intent }), 200);
  const admission = expect(await agentCall(intentPath, { audience, intent, challenge_id: challenge.challenge_id, signature: signed(challenge) }), 202);
  assert.equal(admission.decision, "REQUIRE_APPROVAL");
  assert.equal(admission.result.error, "governance_approval_required");
  const approvalId = admission.result.approval_id;
  assert.ok(approvalId);
  mark(phase, "PASS", { approval_id: approvalId, authentication: "agent_pop", development_only: true });

  set("human_approval");
  const approval = expect(await call(`/api/web/approvals/${approvalId}`), 200);
  assert.equal(approval.requester, agent.agent_id);
  assert.equal(approval.organization_id, agent.organization_id);
  assert.ok(approval.action_digest);
  const resolved = expect(await call(`/api/web/approvals/${approvalId}/resolve`, "POST", { outcome: "APPROVED", notes: "Explicit human approval of harmless local tool" }), 200);
  assert.equal(resolved.status, "APPROVED");
  mark(phase, "PASS", { approval_id: approvalId, action_digest: approval.action_digest });

  set("execution_grant");
  const executed = expect(await call(`/api/web/approvals/${approvalId}/execute`, "POST"), 200);
  assert.equal(executed.execution_status, "SUCCEEDED");
  assert.equal(executed.reconciliation_required, false);
  assert.ok(executed.evidence_id && executed.outcome_id);
  const evidence = expect(await call(`/api/web/evidence/${executed.evidence_id}`), 200);
  assert.equal(evidence.approval_id, approvalId);
  assert.equal(evidence.agent_id, agent.agent_id);
  assert.equal(evidence.identity_id, agent.agent_id);
  assert.equal(evidence.authentication_method, "agent_pop");
  assert.ok(evidence.execution_authorization_id && evidence.execution_nonce_reference);
  mark(phase, "PASS", { permit_type: "ExecutionAuthorization", authorization_id: evidence.execution_authorization_id, nonce_reference: evidence.execution_nonce_reference, evidence_id: executed.evidence_id });
  set("controlled_execution");
  mark(phase, "PASS", { tool: intent.name, evidence_id: executed.evidence_id, outcome_id: executed.outcome_id, execution_status: executed.execution_status });

  set("evidence_verification");
  const verified = expect(await call("/api/web/evidence/verify"), 200);
  assert.equal(verified.chain_intact, true);
  assert.equal(verified.cryptographically_signed, false);
  assert.equal(evidence.organization_id, agent.organization_id);
  assert.equal(evidence.action_type, intent.name);
  assert.ok(evidence.request_fingerprint && evidence.arguments_fingerprint);
  mark(phase, "PASS", { evidence_id: evidence.evidence_id, local_chain_status: verified.status, independently_witnessed: false });
  const before = expect(await call("/api/web/evidence?limit=100"), 200);
  const stale = expect(await agentCall("/api/dev/agent-auth/request-challenge", { audience, intent }), 200);
  const staleProof = signed(stale);
  const staleMessage = JSON.parse(Buffer.from(stale.message, "base64url").toString("utf8"));
  assert.ok(issued.expires_at > Date.now() / 1000, "Revocation must precede natural credential expiry");

  set("revocation");
  const disabled = expect(await call(`${authority}/agents/${agent.agent_id}/disable`, "POST", { reason: "Actual prototype authority revocation" }), 200);
  assert.equal(disabled.status, "DISABLED");
  assert.equal(disabled.agent_id, agent.agent_id);
  assert.ok(disabled.revoked_delegations >= 1);
  const inventory = expect(await call(`${authority}/agents`), 200);
  const persisted = inventory.agents.find(item => item.agent_id === agent.agent_id);
  assert.equal(persisted.lifecycle_state, "DISABLED");
  assert.equal(persisted.has_active_delegation, false);
  mark(phase, "PASS", { agent_id: agent.agent_id, lifecycle_state: persisted.lifecycle_state, revoked_delegations: disabled.revoked_delegations, revocation_epoch: disabled.revocation_epoch });
  set("post_revocation_execution_attempt");
  const denied = await agentCall(intentPath, { audience, intent, challenge_id: stale.challenge_id, signature: staleProof });
  assert.ok(issued.expires_at > Date.now() / 1000, "Expired credential cannot prove revocation");
  assert.ok(staleMessage.expires > Date.now() / 1000, "Expired challenge cannot prove revocation");
  assert.equal(denied.status, 403);
  mark(phase, "PASS", { http_status: denied.status, authentication: "agent_pop" });
  set("post_revocation_denial");
  const replay = await call(`/api/web/approvals/${approvalId}/execute`, "POST");
  assert.equal(replay.status, 409);
  const after = expect(await call("/api/web/evidence?limit=100"), 200);
  assert.deepEqual(after.evidence.map(item => item.evidence_id), before.evidence.map(item => item.evidence_id));
  mark(phase, "PASS", { http_status: denied.status, approval_replay_status: replay.status, evidence_unchanged: true });
}
