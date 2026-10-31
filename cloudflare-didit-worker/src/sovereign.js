/**
 * Mock / adapter for WhitePact sovereign Linux authority (SEC-CF-007).
 * Real Linux runtime undeployed → E2E BLOCKED; this module qualifies the contract locally.
 *
 * Neon is NOT the admission authority — this adapter only mutates durable mirror
 * rows when explicitly invoked as sovereign (PG: whitepact.sovereign_admit=on).
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
 * PostgreSQL sovereign admission — requires whitepact.sovereign_admit=on in txn.
 */
export async function sovereignAdmitPg(pool, { provider, sessionId, admit = true }) {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    await client.query("SELECT set_config('whitepact.sovereign_admit', 'on', true)");
    const cur = await client.query(
      `SELECT status, provider_proofing_status, sovereign_admission, user_id, org_id
         FROM identity_verifications
        WHERE provider=$1 AND provider_reference_id=$2
        FOR UPDATE`,
      [provider, sessionId],
    );
    if (!cur.rowCount) {
      throw new AuthorityDeniedError("VERIFICATION_SESSION_UNKNOWN");
    }
    const row = cur.rows[0];
    const next = sovereignAdmitDecision(
      {
        status: row.status,
        provider_proofing_status: row.provider_proofing_status,
        sovereign_admission: row.sovereign_admission,
      },
      { admit },
    );
    await client.query(
      `UPDATE identity_verifications
          SET status=$3,
              sovereign_admission=$4,
              provider_proofing_status=$5,
              verified_at = CASE WHEN $3='IDENTITY_VERIFIED' THEN now() ELSE verified_at END,
              updated_at = now()
        WHERE provider=$1 AND provider_reference_id=$2`,
      [
        provider,
        sessionId,
        next.status,
        next.sovereign_admission,
        next.provider_proofing_status,
      ],
    );
    await client.query("COMMIT");
    return { ...next, session_id: sessionId, source: "mock_sovereign_pg" };
  } catch (err) {
    try {
      await client.query("ROLLBACK");
    } catch {
      /* ignore */
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
