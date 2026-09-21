export type CapabilityAvailability = "AVAILABLE" | "UNAVAILABLE" | "EXPERIMENTAL";

export type MissionDisposition =
  | "ALLOW"
  | "DENY"
  | "APPROVAL_REQUIRED"
  | "UNKNOWN"
  | "UNREACHABLE";

export type GauntletStatus = "PASS" | "FAIL" | "ERROR" | "UNAVAILABLE";

export type TraceStageStatus = "PRESENT" | "MISSING" | "UNKNOWN";

export type SovereignHttpDisposition = "UNAVAILABLE" | "ERROR";

export type SovereignHttpResult<T> =
  | { ok: true; data: T }
  | { ok: false; status: number; disposition: SovereignHttpDisposition };

export interface OrgRequest {
  organization_id: string;
  environment?: string;
  principal_id?: string;
}

export interface SovereignStatus {
  sovereign_version: string;
  protocol_version: string;
}

export interface FeatureDescriptor {
  name: string;
  availability: CapabilityAvailability;
  version?: string | null;
  read_only?: boolean;
  simulation?: boolean;
  notes?: string | null;
}

export interface SovereignCapabilities {
  sovereign_version: string;
  protocol_version: string;
  features: FeatureDescriptor[];
}

export interface ExplainRequest extends OrgRequest {
  evidence_id?: string;
  identity_id?: string;
}

export interface TraceRequest extends OrgRequest {
  evidence_id: string;
}

export interface AuthorityCompareRequest extends OrgRequest {
  manifest: Record<string, unknown>;
}

export interface BlastRadiusRequest extends OrgRequest {
  actor_identity_id: string;
  hypothetical_extra_capabilities?: string[];
}

export interface MissionRequest extends OrgRequest {
  agent_id: string;
  steps: string[];
}

export interface MissionStep {
  disposition: MissionDisposition;
}

export interface ShadowRequest extends OrgRequest {
  agent_id: string;
  action_type: string;
  target?: string;
  persist?: boolean;
}

export interface PolicyRulesRequest extends OrgRequest {
  rules: Record<string, unknown>[];
}

export interface PolicySimulateRequest extends PolicyRulesRequest {
  action_types: string[];
}

export interface PolicyTestRequest extends OrgRequest {
  cases: Record<string, unknown>[];
}

export interface GauntletRequest extends OrgRequest {
  probe_ids?: string[] | null;
}

export interface GauntletCase {
  status: GauntletStatus;
}

export interface FlightRecorderRequest extends OrgRequest {
  evidence_id: string;
}

export interface TimeMachineRequest extends OrgRequest {
  then_snapshot?: Record<string, unknown> | null;
}

export interface EvidenceCorrelateRequest extends OrgRequest {
  evidence_id: string;
}

export interface CapsuleCreateRequest extends OrgRequest {
  authority_subset?: Record<string, unknown>;
  timeline?: Record<string, unknown>[];
}

export interface CapsuleBodyRequest {
  capsule: Record<string, unknown>;
}
