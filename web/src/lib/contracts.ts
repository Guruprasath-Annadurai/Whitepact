// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT

export type LoadState = "loading" | "success" | "empty" | "error";
export type RecordValue = string | number | boolean | null | string[];
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

export type ApprovalExecutionResponse = {
  approval_id: string;
  result?: unknown;
  error?: "governance_unknown_outcome" | string;
  message?: string;
  evidence_id?: string;
};

export type ConsequentialOutcome =
  | { state: "SUCCESS"; approvalId: string }
  | { state: "DENIED"; approvalId: string }
  | { state: "PENDING"; approvalId: string; required: number; recorded: number }
  | { state: "UNKNOWN"; approvalId: string; message: string; evidenceId?: string }
  | { state: "FAILED"; approvalId: string; message: string };

export type InvitationRecord = DomainRecord & {
  id?: string;
  invitation_id?: string;
  email?: string;
  role?: string;
  status?: string;
  expires_at?: string;
};
