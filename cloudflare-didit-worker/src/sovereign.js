/**
 * Mock / adapter for WhitePact sovereign Linux authority (SEC-CF-007 / 007A).
 * Real Linux runtime undeployed → E2E BLOCKED; this module qualifies the contract locally.
 *
 * Sovereign PG admission MUST use whitepact_sovereign_apply_admission() as
 * session_user=whitepact_sovereign_login. Caller-controlled GUCs are NOT proof.
 */

import { randomUUID } from "node:crypto";
import {
  AuthorityDeniedError,
  PROVIDER_PROOFING,
  SOVEREIGN_ADMISSION,
  SOVEREIGN_STATUS,
  assertExecutionAllowed,
  sovereignAdmitDecision,
} from "./authority_status.js";

/**
 * In-memory sovereign admission against InMemoryIdentityStore.
 */
export function sovereignAdmitInMemory(store, sessionId, { admit = true } = {}) {
  const v = store.verifications.get(sessionId);
  if (!v) throw new AuthorityDeniedError("VERIFICATION_SESSION_UNKNOWN");
  const next = sovereignAdmitDecision(v, { admit });
  store.verifications.set(sessionId, {
    ...v,
    status: next.status,
    sovereign_admission: next.sovereign_admission,
    provider_proofing_status: next.provider_proofing_status,
  });
  return {
    ...next,
    session_id: sessionId,
    source: "mock_sovereign",
  };
}

/**
 * PostgreSQL sovereign admission via SECURITY DEFINER function.
 * Pool MUST connect as whitepact_sovereign_login (distinct non-superuser).
 * Does NOT use set_config('whitepact.sovereign_admit') — that bypass is removed (007A).
 */
export async function sovereignAdmitPg(pool, { provider, sessionId, admit = true }) {
  const client = await pool.connect();
  try {
    const who = await client.query("SELECT session_user AS su, current_user AS cu");
    if (who.rows[0].su !== "whitepact_sovereign_login") {
      throw new AuthorityDeniedError(
        `sovereignAdmitPg requires session_user=whitepact_sovereign_login (got ${who.rows[0].su})`,
        "SOVEREIGN_SESSION_REQUIRED",
      );
    }
    await client.query("BEGIN");
    const res = await client.query(
      `SELECT out_status, out_admission, out_proofing, out_elevates
         FROM whitepact_sovereign_apply_admission($1, $2, $3)`,
      [provider, sessionId, admit],
    );
    if (!res.rowCount) {
      throw new AuthorityDeniedError("VERIFICATION_SESSION_UNKNOWN");
    }
    const row = res.rows[0];
    await client.query("COMMIT");
    return {
      status: row.out_status,
      sovereign_admission: row.out_admission,
      provider_proofing_status: row.out_proofing,
      identity_transition: row.out_elevates === true,
      elevates: row.out_elevates === true,
      execution_granted: row.out_status === SOVEREIGN_STATUS.IDENTITY_VERIFIED,
      session_id: sessionId,
      source: "mock_sovereign_pg_definer",
    };
  } catch (err) {
    try {
      await client.query("ROLLBACK");
    } catch {
      /* ignore */
    }
    if (err instanceof AuthorityDeniedError) throw err;
    const msg = err.message || String(err);
    if (/PROVIDER_EVIDENCE_REQUIRED/.test(msg)) {
      throw new AuthorityDeniedError(msg, "PROVIDER_EVIDENCE_REQUIRED");
    }
    if (/REOPEN_FORBIDDEN/.test(msg)) {
      throw new AuthorityDeniedError(msg, "REOPEN_FORBIDDEN");
    }
    if (/VERIFICATION_SESSION_UNKNOWN|P0002/.test(msg)) {
      throw new AuthorityDeniedError(msg, "VERIFICATION_SESSION_UNKNOWN");
    }
    if (/42501|SEC-CF-007A|denied for session_user/.test(msg)) {
      throw new AuthorityDeniedError(msg, "SOVEREIGN_ADMISSION_DENIED");
    }
    throw err;
  } finally {
    client.release();
  }
}

/**
 * Record fail-closed denial when execution is attempted without sovereign admit.
 */
export async function recordAuthorityDenialPg(
  pool,
  { provider, sessionId, userId, orgId, reasonCode },
) {
  await pool.query(
    `INSERT INTO identity_authority_denials
       (id, provider, session_id, user_id, org_id, reason_code)
     VALUES ($1,$2,$3,$4,$5,$6)`,
    [randomUUID(), provider, sessionId, userId || null, orgId || null, reasonCode],
  );
}

export function checkExecutionOrDeny(verification) {
  try {
    return assertExecutionAllowed(verification);
  } catch (err) {
    if (err instanceof AuthorityDeniedError) {
      return {
        execution_granted: false,
        denied: true,
        code: err.code,
        message: err.message,
        authority_offline_or_pending:
          err.code === "SOVEREIGN_ADMISSION_REQUIRED" ||
          verification?.provider_proofing_status === PROVIDER_PROOFING.APPROVED,
      };
    }
    throw err;
  }
}

export {
  AuthorityDeniedError,
  PROVIDER_PROOFING,
  SOVEREIGN_ADMISSION,
  SOVEREIGN_STATUS,
  assertExecutionAllowed,
};
