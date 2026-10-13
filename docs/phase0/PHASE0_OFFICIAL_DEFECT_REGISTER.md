# Phase 0 — Official defect register (Antigravity Global Enterprise Audit)

Source of truth for IDs and titles: [ANTIGRAVITY_GLOBAL_ENTERPRISE_AUDIT_2026-09-30.md](./ANTIGRAVITY_GLOBAL_ENTERPRISE_AUDIT_2026-09-30.md).

**Audit SHA `3c955c7`:** not resolvable — reproduction uses verifiable baselines in [PHASE0_REPRODUCTION_MATRIX.md](./PHASE0_REPRODUCTION_MATRIX.md). No full SHA invented.

**Verification labels:** `REPORT_ONLY` | `REPRODUCED` | `PARTIALLY_MITIGATED` | `CONTRADICTED_BY_EVIDENCE` | `VERIFIED_CLOSED`

**Owner:** **Cursor** for all product rows (React SaaS dashboard, approvals, policies, team, backend, SDKs, runtime, infra). **Codex** — public corporate website only. **Antigravity** — independent validation.

| ID | Sev | Title (official) | Baseline | Evidence (Cursor) | Verification | Phase 1 owner |
|----|-----|------------------|----------|-------------------|--------------|---------------|
| BLK-P0-01 | P0 | CLI launches BiasBuster instead of WhitePact. | B-main `81beb3a` | `pyproject.toml`: `whitepact = "biasbuster.cli:main"`; `whitepact --help` → “BiasBuster — open-source bias testing” | **REPRODUCED** | Cursor |
| BLK-P0-02 | P0 | Stdio MCP transport bypasses governance. | B-main | WS-2 enterprise trust domain + stdio fail-closed (PR #130) | **VERIFIED_CLOSED** (Antigravity M1) | Antigravity |
| BLK-P0-03 | P0 | Core authority kernel disconnected from running services. | B-main | WS-2 authority binding on hosted/enterprise paths (PR #130) | **VERIFIED_CLOSED** (Antigravity M1) | Antigravity |
| BLK-P0-04 | P0 | Web approvals table is read-only. | B-main | WS-3: full browser lifecycle in `customer-journey.e2e.mjs`; web API resolve/execute + RBAC in `test_v1_web_contract_closure.py` / `test_web_policy_management.py` | **CLOSED BY ENGINEERING** (WS-3); independent audit pending | Cursor |
| BLK-P0-05 | P0 | Published package/product naming mismatch. | B-main + PyPI | Project name `rai-governance-platform`; CLI/product `whitepact` → BiasBuster; `docs/PACKAGE_IDENTITY.md` on main | **REPRODUCED** | Cursor |
| BLK-P0-06 | P0 | Dual-frontend routing and authentication collision. | B-main | WS-3: `legacy_frontend.py` hard-retires legacy governance shells when unified SaaS; regression tests + E2E | **CLOSED BY ENGINEERING** (WS-3); independent audit pending | Cursor |
| BLK-P1-01 | P1 | Policy Management UI absent. | B-main | WS-3: `/dashboard/policy`, `PolicyPage.tsx`, `/api/v1/web/policy*` + `test_web_policy_management.py` | **CLOSED BY ENGINEERING** (WS-3); independent audit pending | Cursor |
| BLK-P1-02 | P1 | Team invitation workflow unwired. | B-main | UI + `/api/v1/web/invitations` exist; end-to-end email/delivery not verified in Phase 0 | **PARTIALLY_MITIGATED** | Cursor |
| BLK-P1-03 | P1 | SDKs lack WhitePact runtime governance methods. | B-main | `sdk/typescript/src/client.ts`: REST eval/trust APIs; no first-class governance runtime helpers | **REPRODUCED** | Cursor |
| BLK-P1-04 | P1 | Billing operates in mock/unverified mode. | B-main | `PaddleBillingService` gated on `settings.paddle_api_key`; without keys, console behaves unconfigured — **Paddle** (not Stripe) | **REPRODUCED** when unconfigured; **PARTIALLY_MITIGATED** on PR #107 Paddle closure | Cursor |
| BLK-P1-05 | P1 | Active execution interruption during break-glass is absent or unverified. | B-main | No dedicated break-glass interrupt path found in governance executors; LangGraph `interrupt()` is integration-only | **REPRODUCED** | Cursor |
| BLK-P1-06 | P1 | Automated audit/SIEM streaming unimplemented. | B-main | SIEM fields on incidents; no continuous streaming export pipeline | **REPRODUCED** | Cursor |
| BLK-P1-07 | P1 | Account deletion and sensitive audit-data erasure incomplete. | B-main | No complete account+audit erasure workflow located in Phase 0 scan | **REPRODUCED** | Cursor |
| BLK-P1-08 | P1 | Cloud load balancer/origin protection incomplete. | B-cloud PR #128 | Terraform modules present; live LB/origin proof absent; overlaps CLOUD-AG-07 | **REPRODUCED** (design); live **REPORT_ONLY** | Cursor |
| BLK-P2-01 | P2 | PostgreSQL worker-lease contention. | B-main | Phase 7a worker lease design in docs/runtime; contention handling not re-benchmarked in Phase 0 | **REPORT_ONLY** | Cursor |
| BLK-P2-02 | P2 | Enterprise SSO/SCIM gaps. | B-main | SAML/OIDC config exists; SCIM not located; `sso_required` org flag | **REPRODUCED** | Cursor |
| BLK-P2-03 | P2 | Accessibility violations. | B-main | CI runs WCAG job; full violation inventory not re-run in Phase 0 | **REPORT_ONLY** | Cursor |
| BLK-P2-04 | P2 | Distributed tracing gaps. | B-main | OTEL hooks referenced; end-to-end trace completeness not proven | **REPORT_ONLY** | Cursor |
| BLK-P2-05 | P2 | Audit query/indexing concerns. | B-main | Audit log APIs + static viewer; indexing at scale not proven | **REPORT_ONLY** | Cursor |
| BLK-P2-06 | P2 | Automated restore verification absent. | B-main / B-cloud | Backup docs on cloud branch; automated restore drill not executed | **REPRODUCED** | Cursor |
| BLK-P3-01 | P3 | Legacy domain references. | B-main | `rai://` / ResponsibleAI strings in compliance and legacy assets | **REPRODUCED** | Cursor |
| BLK-P3-02 | P3 | Inadequate developer documentation. | B-main | Large doc surface; enterprise onboarding path fragmented | **REPORT_ONLY** | Cursor |
| BLK-P3-03 | P3 | Legacy BiasBuster/PrivacyLabel source overhang. | B-main | Wheel includes `biasbuster`, `privacylabel` packages | **REPRODUCED** | Cursor |
| BLK-P3-04 | P3 | Modal accessibility and interaction polish. | B-main | `AccessibleDialog` used; full modal a11y audit not re-run | **REPORT_ONLY** | Cursor |

## Cloud audit cross-reference

See [ANTIGRAVITY_CLOUD_PRESTAGING_AUDIT_REGISTER.md](./ANTIGRAVITY_CLOUD_PRESTAGING_AUDIT_REGISTER.md) — verdict **BLOCKED — UNSAFE TO PROVISION**. Cloud findings are **not** duplicates of the global 24; they gate provisioning.

## Supplemental engineering findings

Cursor-only discoveries (DNS egress closure on `main`, IoT surface absent, RC branch fragmentation, etc.) live in [PHASE0_SUPPLEMENTAL_ENGINEERING_REGISTER.md](./PHASE0_SUPPLEMENTAL_ENGINEERING_REGISTER.md) and **must not** replace rows in this table.
