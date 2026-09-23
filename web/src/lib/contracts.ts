// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT

export type LoadState = "loading" | "success" | "empty" | "error";
export type RecordValue = string | number | boolean | null | string[] | Record<string, unknown> | unknown[];
export type DomainRecord = Record<string, RecordValue>;

export type DomainResponse = {
  items: DomainRecord[];
  source: string;
  billing_configured?: boolean;
  detail?: string;
};

export type ApprovalResolution = {
  status: "PENDING" | "APPROVED" | "DENIED" | string;
  required_approvals?: number;
};

export type ApprovalVote = {
  vote_id: string;
  resolver_identity_id: string;
  outcome: "APPROVED" | "DENIED" | string;
  notes?: string | null;
  resolved_at: string;
};

export type ApprovalDetail = {
  approval_id: string;
  status: "PENDING" | "APPROVED" | "DENIED" | "CONSUMED" | string;
  action_type: string;
  target: string;
  risk_tier?: string | null;
  requester?: string | null;
  requested_by?: string | null;
  required_approvals: number;
  current_vote_count: number;
  approved_vote_count?: number;
  denied_vote_count?: number;
  votes: ApprovalVote[];
  purpose?: string | null;
  argument_summary?: { argument_keys: string[]; argument_count: number };
  requested_at?: string;
  expires_at?: string | null;
  resolved_at?: string | null;
  execution_state?: string;
};

export type ApprovalExecutionResponse = {
  approval_id: string;
  execution_status: "SUCCEEDED" | "FAILED" | "UNKNOWN" | "NOT_ATTEMPTED" | string;
  reconciliation_required: boolean;
  evidence_id: string | null;
  outcome_id: string | null;
  message: string;
};

export type ConsequentialOutcome =
  | { state: "SUCCESS"; approvalId: string; message: string; evidenceId?: string; outcomeId?: string }
  | { state: "DENIED"; approvalId: string }
  | { state: "PENDING"; approvalId: string; required: number; recorded: number }
  | { state: "UNKNOWN"; approvalId: string; message: string; reconciliationRequired: boolean; evidenceId?: string; outcomeId?: string }
  | { state: "FAILED"; approvalId: string; message: string };

export type InvitationRecord = DomainRecord & {
  id?: string;
  invitation_id?: string;
  email?: string;
  role?: string;
  status?: string;
  expires_at?: string;
};

export type EvidenceListResponse = { evidence: DomainRecord[]; limit: number };
export type EvidenceVerification = {
  org_id: string;
  status: "VALID" | "INCOMPLETE" | "INVALID" | string;
  chain_intact: boolean;
  cryptographically_signed: false;
  integrity_note: string;
};
export type EvidenceAttestation = {
  evidence_id: string;
  action_id: string;
  decision: string;
  risk_tier?: string | null;
  evidence_hash?: string | null;
  outcome_status?: string | null;
  reconciliation_status: string;
  attested_at: string;
  integrity_note: string;
  cryptographically_signed: false;
};
