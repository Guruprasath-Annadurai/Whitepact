export type CapabilityAvailability = "AVAILABLE" | "UNAVAILABLE" | "EXPERIMENTAL";

export type MissionDisposition =
  | "ALLOW"
  | "DENY"
  | "APPROVAL_REQUIRED"
  | "UNKNOWN"
  | "UNREACHABLE";

export type GauntletStatus = "PASS" | "FAIL" | "ERROR" | "UNAVAILABLE";

export type SovereignHttpResult<T> =
  | { ok: true; data: T }
  | { ok: false; status: number; disposition: "UNAVAILABLE" | "ERROR" };
