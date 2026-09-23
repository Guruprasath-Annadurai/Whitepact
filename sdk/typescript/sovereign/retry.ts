/** Mirrors Python SDK RETRY_MAP — classification only; no blind effectful retries. */

export type RetryClass =
  | "SAFE_TO_RETRY"
  | "CONDITIONALLY_RETRYABLE"
  | "NEVER_BLINDLY_RETRY";

export const RETRY_MAP: Record<string, RetryClass> = {
  status: "SAFE_TO_RETRY",
  capabilities: "SAFE_TO_RETRY",
  xray: "SAFE_TO_RETRY",
  explain: "SAFE_TO_RETRY",
  trace: "SAFE_TO_RETRY",
  effective: "SAFE_TO_RETRY",
  compare: "SAFE_TO_RETRY",
  drift: "SAFE_TO_RETRY",
  simulate_blast_radius: "NEVER_BLINDLY_RETRY",
  simulate_mission: "NEVER_BLINDLY_RETRY",
  shadow: "NEVER_BLINDLY_RETRY",
  policy_lint: "NEVER_BLINDLY_RETRY",
  policy_test: "NEVER_BLINDLY_RETRY",
  policy_diff: "NEVER_BLINDLY_RETRY",
  policy_simulate: "NEVER_BLINDLY_RETRY",
  gauntlet: "NEVER_BLINDLY_RETRY",
  flight_recorder: "NEVER_BLINDLY_RETRY",
  time_machine: "NEVER_BLINDLY_RETRY",
  evidence_correlate: "NEVER_BLINDLY_RETRY",
  capsule_create: "NEVER_BLINDLY_RETRY",
  capsule_validate: "NEVER_BLINDLY_RETRY",
  capsule_reproduce: "NEVER_BLINDLY_RETRY",
  authority_bom: "NEVER_BLINDLY_RETRY",
};

export function retryClass(operation: string): RetryClass {
  return RETRY_MAP[operation] ?? "CONDITIONALLY_RETRYABLE";
}

/** Max transient GET retries for SAFE_TO_RETRY read-only endpoints (network errors only). */
export const SAFE_GET_MAX_ATTEMPTS = 2;
