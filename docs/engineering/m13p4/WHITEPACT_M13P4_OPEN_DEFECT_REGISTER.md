# M13-P4 open defect and qualification register

GLOBAL PRODUCTION NO-GO. Security-owner closure claims remain independently unverified; this product register does not overwrite their findings.

| ID | Priority / disposition | Evidence and remaining requirement |
| --- | --- | --- |
| P4-MCP-01 | Reliability RESOLVED in test fixture | Exact baseline and deterministic prior-shutdown failures traced to SSE process-global shutdown state; fixture-only reset preserves assertions; 7 focused and 42 expanded MCP tests pass. No production revocation/protected-execution defect is claimed fixed. |
| P4-INV-01 | P1 BLOCKED: application inventory and ownership | No integrated customer endpoint/schema exists. Do not invent API routes, ownership or successful creation. |
| P4-INV-02 | P1 PARTIAL: agent inventory | Supported tenant-scoped read integrated and tested; backend has no pagination/total count or executable capability contract. Local filtering/pages apply only to loaded records, not complete inventory. No mutations enabled. |
| P4-SEC-01 | P0 BLOCKED: independent security acceptance | Original concurrency, crash, quorum, WebAuthn and containment groups must pass independently on one reviewed unified commit. Read-only preflight is preservation evidence only. |
| P4-SEC-02 | P0 BLOCKED: candidate/owner coordination | M13-S4 is available at `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc`; owner reports P0-A through E closed. Product starts from issued M13-R3; no S4 integration or independent acceptance supplied. |
| P4-JOURNEY-01 | P0 BLOCKED: golden journey | Fresh customer identity → passkey/consent/root → application/agent/delegation → real controlled action/evidence/revocation is not demonstrated. Fixture authentication is not customer acceptance. |
| P4-ONBOARD-01 | P1 BLOCKED: privileged onboarding and organization switching | UI preparation and current session reads do not qualify membership switching, passkeys, consent, root bootstrap/recovery or execution authority. |
| P4-SDK-01 | P1 PARTIAL: optional integrations | 39 adapter tests pass; 32 skip for missing optional OpenAI Agents, CrewAI and LlamaIndex dependencies. Installed external A2A SDK is not demonstrated. No universal framework compatibility claim. |
| P4-UX-01 | P2 PARTIAL: accessibility scope | Actual Chromium, axe, keyboard and viewport checks apply to recorded public/fixture screens. No screen-reader application or complete real authenticated golden journey qualification performed. |
| S4-P1-01 | P1 PENDING FOUNDER | Owner flags 300-second Path B ticket lifetime for possible reduction to 120 seconds. No product policy change or ratification. |
| S4-P1-02 | P1 OPEN ENVIRONMENT GATE | Native Linux host/container evidence still required; macOS skips cannot qualify Linux kernel behavior. No M14 work performed. |
| S4-P1-03 | Owner documentation reconciliation preserved | Evidence is a linear SHA-256 chain; no invented Merkle proof or independent certification. |
| S4-P2 | Owner dispositions preserved | Coverage/runtime and sensitive recovery/containment frontend synchronization remain subject to existing review and qualification rules. No test skip or reduced assertion introduced here. |

Existing source/security findings under `docs/security/` and all eight original reproducer files remain unchanged. The safe unblocked product work is complete to the supported read/UI contracts; blocked backend capabilities are not replaced with cosmetic or synthetic behavior.
