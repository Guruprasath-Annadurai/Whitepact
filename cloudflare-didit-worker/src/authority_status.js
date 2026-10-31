/**
 * SEC-CF-007 — Authority boundary between Didit provider proofing and
 * WhitePact sovereign identity admission.
 *
 * Edge (CF Workers + Neon webhook role) may record PROVIDER_* proofing only.
 * IDENTITY_VERIFIED / execution grants require WhitePact sovereign Linux authority.
 * This module is policy + pure mapping — Neon is NOT an admission service.
 */

/** Provider proofing labels (non-authoritative). */
export const PROVIDER_PROOFING = Object.freeze({
  APPROVED: "PROVIDER_APPROVED",
  REJECTED: "PROVIDER_REJECTED",
  REVIEW: "PROVIDER_REVIEW",
  SUSPENDED: "PROVIDER_SUSPENDED",
});

/** Sovereign WhitePact identity status (authoritative). */
export const SOVEREIGN_STATUS = Object.freeze({
  REVIEW_REQUIRED: "REVIEW_REQUIRED",
  IDENTITY_VERIFIED: "IDENTITY_VERIFIED",
  REJECTED: "REJECTED",
  SUSPENDED: "SUSPENDED",
});

/** Sovereign admission workflow flags. */
export const SOVEREIGN_ADMISSION = Object.freeze({
  PENDING: "PENDING",
  ADMITTED: "ADMITTED",
  DENIED: "DENIED",
  REVOCATION_PENDING: "REVOCATION_PENDING",
});

/** Didit webhook status → provider proofing (never IDENTITY_VERIFIED). */
const DIDIT_TO_PROOFING = Object.freeze({
  Approved: PROVIDER_PROOFING.APPROVED,
  Declined: PROVIDER_PROOFING.REJECTED,
  "In Review": PROVIDER_PROOFING.REVIEW,
  "Not Started": PROVIDER_PROOFING.REVIEW,
  "In Progress": PROVIDER_PROOFING.REVIEW,
  Resubmitted: PROVIDER_PROOFING.REVIEW,
  Expired: PROVIDER_PROOFING.REJECTED,
  Abandoned: PROVIDER_PROOFING.REJECTED,
  "Kyc Expired": PROVIDER_PROOFING.SUSPENDED,
});

export function mapDiditStatusToProviderProofing(diditStatus) {
  const proofing = DIDIT_TO_PROOFING[diditStatus];
  if (!proofing) return null;
  return proofing;
}

/**
 * Apply a verified signed Didit outcome at the EDGE.
 * Must never return sovereign status IDENTITY_VERIFIED.
 *
 * @param {object} args
 * @param {string} args.currentSovereignStatus
 * @param {string|null} args.currentAdmission
 * @param {string} args.providerProofing
 */
export function applyEdgeProviderOutcome({
  currentSovereignStatus,
  currentAdmission = null,
  providerProofing,
}) {
  if (!providerProofing) {
    throw new Error("unsupported provider proofing");
  }

  const wasVerified = currentSovereignStatus === SOVEREIGN_STATUS.IDENTITY_VERIFIED;

  // Fail-closed demotion: sovereign-verified subject later declined / expired / kyc-expired.
  if (
    wasVerified &&
    (providerProofing === PROVIDER_PROOFING.REJECTED ||
      providerProofing === PROVIDER_PROOFING.SUSPENDED)
  ) {
    return {
      provider_proofing_status: providerProofing,
      status: SOVEREIGN_STATUS.SUSPENDED,
      sovereign_admission: SOVEREIGN_ADMISSION.REVOCATION_PENDING,
      identity_transition: false,
      elevates: false,
      sovereign_admission_required: true,
      execution_granted: false,
    };
  }

  // Never reopen REJECTED / SUSPENDED via Approved at the edge.
  if (
    (currentSovereignStatus === SOVEREIGN_STATUS.REJECTED ||
      currentSovereignStatus === SOVEREIGN_STATUS.SUSPENDED) &&
    providerProofing === PROVIDER_PROOFING.APPROVED
  ) {
    return {
      provider_proofing_status: providerProofing,
      status: currentSovereignStatus,
      sovereign_admission:
        currentAdmission || SOVEREIGN_ADMISSION.DENIED,
      identity_transition: false,
      elevates: false,
      sovereign_admission_required: true,
      execution_granted: false,
      reopen_blocked: true,
    };
  }

  if (providerProofing === PROVIDER_PROOFING.APPROVED) {
    // Evidence only — sovereign remains REVIEW_REQUIRED (or stays IDENTITY_VERIFIED
    // if already sovereign-admitted; edge does not elevate).
    return {
      provider_proofing_status: PROVIDER_PROOFING.APPROVED,
      status: wasVerified
        ? SOVEREIGN_STATUS.IDENTITY_VERIFIED
        : SOVEREIGN_STATUS.REVIEW_REQUIRED,
      sovereign_admission: wasVerified
        ? SOVEREIGN_ADMISSION.ADMITTED
        : SOVEREIGN_ADMISSION.PENDING,
      identity_transition: false,
      elevates: false,
      sovereign_admission_required: !wasVerified,
      execution_granted: false,
    };
  }

  if (providerProofing === PROVIDER_PROOFING.REJECTED) {
    return {
      provider_proofing_status: PROVIDER_PROOFING.REJECTED,
      status: SOVEREIGN_STATUS.REJECTED,
      sovereign_admission: SOVEREIGN_ADMISSION.DENIED,
      identity_transition: false,
      elevates: false,
      sovereign_admission_required: false,
      execution_granted: false,
    };
  }

  if (providerProofing === PROVIDER_PROOFING.SUSPENDED) {
    return {
      provider_proofing_status: PROVIDER_PROOFING.SUSPENDED,
      status: wasVerified
        ? SOVEREIGN_STATUS.SUSPENDED
        : SOVEREIGN_STATUS.REVIEW_REQUIRED,
      sovereign_admission: wasVerified
        ? SOVEREIGN_ADMISSION.REVOCATION_PENDING
        : SOVEREIGN_ADMISSION.PENDING,
      identity_transition: false,
      elevates: false,
      sovereign_admission_required: true,
      execution_granted: false,
    };
  }

  // REVIEW family
  return {
    provider_proofing_status: PROVIDER_PROOFING.REVIEW,
    status: wasVerified
      ? SOVEREIGN_STATUS.IDENTITY_VERIFIED
      : SOVEREIGN_STATUS.REVIEW_REQUIRED,
    sovereign_admission: wasVerified
      ? SOVEREIGN_ADMISSION.ADMITTED
      : SOVEREIGN_ADMISSION.PENDING,
    identity_transition: false,
    elevates: false,
    sovereign_admission_required: !wasVerified,
    execution_granted: false,
  };
}

/**
 * Execution / org-permission gate. Fail closed when sovereign offline or
 * subject is only PROVIDER_APPROVED.
 */
export class AuthorityDeniedError extends Error {
  constructor(
    message = "WhitePact sovereign authority has not admitted this identity.",
    code = "SOVEREIGN_ADMISSION_REQUIRED",
  ) {
    super(message);
    this.name = "AuthorityDeniedError";
    this.code = code;
    this.httpStatus = 403;
    this.execution_granted = false;
  }
}

export function assertExecutionAllowed(verification) {
  if (!verification) {
    throw new AuthorityDeniedError("No verification record.", "VERIFICATION_MISSING");
  }
  if (verification.status !== SOVEREIGN_STATUS.IDENTITY_VERIFIED) {
    throw new AuthorityDeniedError(
      verification.provider_proofing_status === PROVIDER_PROOFING.APPROVED
        ? "Provider approved but sovereign admission pending or offline."
        : "Identity is not sovereign-verified.",
      verification.provider_proofing_status === PROVIDER_PROOFING.APPROVED
        ? "SOVEREIGN_ADMISSION_REQUIRED"
        : "IDENTITY_NOT_VERIFIED",
    );
  }
  if (verification.sovereign_admission !== SOVEREIGN_ADMISSION.ADMITTED) {
    throw new AuthorityDeniedError(
      "Sovereign admission flag is not ADMITTED.",
      "SOVEREIGN_ADMISSION_REQUIRED",
    );
  }
  return { execution_granted: true };
}

/**
 * Mock sovereign Linux authority for local/PG tests when real runtime undeployed.
 * ONLY this path may set IDENTITY_VERIFIED.
 */
export function sovereignAdmitDecision(verification, { admit = true } = {}) {
  if (!verification) throw new AuthorityDeniedError("No verification record.");
  if (verification.provider_proofing_status !== PROVIDER_PROOFING.APPROVED) {
    throw new AuthorityDeniedError(
      "Sovereign will not admit without PROVIDER_APPROVED evidence.",
      "PROVIDER_EVIDENCE_REQUIRED",
    );
  }
  if (
    verification.status === SOVEREIGN_STATUS.REJECTED ||
    verification.status === SOVEREIGN_STATUS.SUSPENDED
  ) {
    throw new AuthorityDeniedError(
      "Sovereign will not reopen rejected/suspended via silent admit.",
      "REOPEN_FORBIDDEN",
    );
  }
  if (!admit) {
    return {
      status: SOVEREIGN_STATUS.REJECTED,
      sovereign_admission: SOVEREIGN_ADMISSION.DENIED,
      provider_proofing_status: verification.provider_proofing_status,
      identity_transition: false,
      elevates: false,
      execution_granted: false,
    };
  }
  return {
    status: SOVEREIGN_STATUS.IDENTITY_VERIFIED,
    sovereign_admission: SOVEREIGN_ADMISSION.ADMITTED,
    provider_proofing_status: verification.provider_proofing_status,
    identity_transition: true,
    elevates: true,
    execution_granted: true,
  };
}
