// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { Link, useOutletContext } from "react-router-dom";
import type { WebSession } from "./DashboardShell";

export function AccountPage() {
  const session = useOutletContext<WebSession>();
  return <main className="dashboard-content" style={{ overflowWrap: "anywhere" }}>
    <div className="page-heading"><div><h1>Account</h1><p>Details returned by your authenticated session.</p></div></div>
    <section className="data-panel" aria-labelledby="account-details-heading">
      <h2 id="account-details-heading">Signed-in account</h2>
      <dl><div><dt>Name</dt><dd>{session.user.full_name}</dd></div><div><dt>Email</dt><dd>{session.user.email}</dd></div></dl>
      <p>This read-only view does not confirm identity assurance, email verification or execution authority.</p>
    </section>
    <section className="data-panel" aria-labelledby="account-access-heading">
      <h2 id="account-access-heading">Account access</h2>
      <p>Use the existing email reset flow to request a password change. Delivery depends on this deployment's configured mail service; opening the flow does not change your password.</p>
      <Link to="/forgot-password">Request a password reset</Link>
      <p><Link to="/dashboard/security">Read backend security posture</Link></p>
      <p>Passkey enrollment, recovery-factor changes, email changes and account deletion are unavailable from this page. Their security contracts require independent qualification.</p>
    </section>
    <section className="data-panel" aria-labelledby="account-workspace-heading">
      <h2 id="account-workspace-heading">Current workspace</h2>
      <p>{session.organization?.name ?? "No organization selected"}</p>
      <p>Organization membership is separate from effective permission to execute an action.</p>
      <Link to="/dashboard/organization">Read organization details</Link>
    </section>
  </main>;
}
