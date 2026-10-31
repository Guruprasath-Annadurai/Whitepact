/**
 * Distinct non-superuser PG logins for SEC-CF-007C privilege proofs.
 * Lab passwords only — never production secrets.
 */
import pg from "pg";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dir = dirname(fileURLToPath(import.meta.url));

export const ADMIN_URL =
  process.env.DATABASE_URL || "postgres://ubuntu@127.0.0.1:54329/m13_didit";

export const EDGE_URL =
  process.env.WHITEPACT_EDGE_DATABASE_URL ||
  "postgres://whitepact_edge_login:edge-lab-only-not-prod@127.0.0.1:54329/m13_didit";

export const SOVEREIGN_URL =
  process.env.WHITEPACT_SOVEREIGN_DATABASE_URL ||
  "postgres://whitepact_sovereign_login:sovereign-lab-only-not-prod@127.0.0.1:54329/m13_didit";

export const RECONCILE_URL =
  process.env.WHITEPACT_RECONCILE_DATABASE_URL ||
  "postgres://whitepact_reconcile_login:reconcile-lab-only-not-prod@127.0.0.1:54329/m13_didit";

export function createPool(url) {
  return new pg.Pool({ connectionString: url, max: 5 });
}

export async function applyAllSchemas(adminPool) {
  for (const f of [
    "001_identity_events.sql",
    "002_reconciliation_jobs.sql",
    "003_authority_boundary.sql",
    "004_database_hardening.sql",
  ]) {
    await adminPool.query(readFileSync(join(__dir, "../schema", f), "utf8"));
  }
}

export async function truncateIdentityTables(adminPool) {
  await adminPool.query(
    `TRUNCATE identity_authority_denials,
              identity_webhook_delivery_ops,
              identity_reconciliation_jobs,
              identity_reconciliation_deadletters,
              identity_provider_events,
              identity_verifications,
              identity_session_bindings`,
  );
}

export async function assertSessionUser(pool, expected) {
  const r = await pool.query("SELECT session_user AS su, current_user AS cu, rolsuper FROM pg_roles WHERE rolname = session_user");
  if (r.rows[0].su !== expected) {
    throw new Error(`expected session_user=${expected}, got ${r.rows[0].su}`);
  }
  if (r.rows[0].rolsuper === true) {
    throw new Error(`session_user ${expected} must not be superuser`);
  }
  return r.rows[0];
}
