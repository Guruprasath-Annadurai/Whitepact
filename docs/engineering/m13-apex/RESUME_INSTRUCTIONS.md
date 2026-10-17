# APEX checkpoint — GLOBAL PRODUCTION NO-GO

Status: PARTIAL engineering; mandatory customer acceptance BLOCKED.
This checkpoint is not M13 completion or permission to enable privileged workflows.

## Provenance

Integration branch: `codex/whitepact-m13-apex-integration`, based on Forge
`9fc9f94873d645ce36239e44eef6919a8604bdc7` (tree
`61393e3e6a9128c0e4dbd51e533a0f023f840e5c`). Review PR must target
`codex/whitepact-m13-forge-product`, not main. Existing worktrees were preserved.
No TITAN security implementation has been integrated at this checkpoint.

Security candidate independently exercised:
`40e43440489eebde6886af014943ea18ed228b68`, tree
`c6b106db0974838f084e391ca8f8b2f084c45882`.

## Implemented and independently exercised

- Directory descriptive metadata now round-trips through direct, identifier and
  search reads. Tenant and lifecycle predicates remain unchanged. Metadata is
  not interpreted as authority. New tests exercise SQLite and a genuinely
  migrated disposable PostgreSQL database, including four concurrent claims.
- MCP `rai_check_trust` now declares its external HTTP boundary through
  `openWorldHint=true`; its description identifies an advisory service report.
  Regression calls the actual client against a local HTTP server.
- Separate APEX browser harness uses actual signup, delivered email verification,
  password login, organization creation, Chrome WebAuthn ceremonies and logout.
  Original I3, Forge and independent upgrade reproducers remain unchanged.
- Receipt validation rejects seeded authority, contradictory success, duplicate
  stages and success after missing prerequisites. These unit tests are receipt
  integrity evidence, not customer acceptance.

## Results from this working-tree checkpoint

- Directory/MCP: **45 passed, zero skipped**, 22.78 seconds.
  Command: `PYTHONPATH=src:. python -m pytest tests/test_m13_apex_directory.py tests/test_principal_directory.py tests/test_m13_apex_mcp_metadata.py tests/test_mcp_directory_conformance.py -q -o addopts=''`.
- Receipt integrity: **4 passed**, 1.68 seconds.
- Metadata red reproduction: **2 failed**, one per database, on missing metadata.
  Earlier harness enum error was corrected; it is not a product defect.
  Intermediate read-projection mistakes were caught and corrected before the
  passing directory run; only the final run qualifies the implementation.
- Unchanged upgrade reproducer at `18a0086141bda2477a60972483517c1f3f613abf`
  independently upgraded clean c9a4436c schema 0064 to clean 40e43440 schema 0065;
  required column absent before, present after. PASS, no seeded authority.
  This does not yet prove data retention or downgrade disposition.
- Genuine new-candidate customer run: **8 PASS, 1 BLOCKED, 15 NOT_EXECUTED**.
  Passes include real WebAuthn enrollment/assertion, elevated-session cookie and
  CSRF rotation, original session denial (401), and logout invalidation (401).
  Root initiation returns **403 IDENTITY_ASSURANCE_REQUIRED**. Required identity
  assurance stayed enabled. No provider fixture, seeded root, forged credential,
  synthetic consent, delegation or execution substituted for acceptance.
  Chromium virtual authenticator evidence is not physical hardware certification.

Local raw receipts: `/private/tmp/apex-directory-mcp-verified.log`,
`/private/tmp/apex-40e-original-upgrade.json`,
`/private/tmp/apex-40e-real-customer.json`. These runs precede the authored commit;
their harness Git identity correctly records a dirty tree. Exact committed-head
validation and CI are required separately; do not relabel these runs exact-head.

## Next work and blockers

1. Preserve migration ownership with TITAN. Independently qualify 40e43440 fresh
   migrations, upgrades/data retention and original security regressions before
   integrating selected changes. Its branch also changes a copied reproducer;
   do not overwrite the preserved original independent probe.
2. Hand the real identity-assurance boundary to TITAN-1. Establish a supported
   customer identity qualification contract; never disable the requirement to
   advance the journey. Consent/root and all downstream authority stages remain
   unqualified. The 300-second Path B founder decision remains pending.
3. Complete broad feature inventory, customer matrix and remaining requested
   APEX reports. Existing Forge security, DCO, CI, Gitleaks and merge-tree issues
   remain open; no policy suppression or history rewrite is authorized.
4. Run committed-head regression and CI, then continue unrelated safe product
   integration. Platform provider verification, full MCP/OAuth transport matrix,
   native Linux enforcement and complete golden journey are not qualified by
   this checkpoint. Do not claim missing acceptance from copied results.

No merge, deployment, cloud resources, package publication or external listing
submission occurred. No M14 or M21 work is authorized.
