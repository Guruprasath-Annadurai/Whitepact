# whitepact.yaml (Sovereign Manifest)

The manifest declares **expected authority only**.

It does **not**:

- grant capabilities
- create approvals
- issue execution authorizations

Sovereign compares manifest expectations to **effective authority** derived from:

- active delegations (`DelegationRepository`)
- org authority ceiling (`OrgAuthorityCeilingRepository`)

Secret-like metadata keys are rejected at validation time.
