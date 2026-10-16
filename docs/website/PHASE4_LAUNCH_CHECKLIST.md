<!-- Copyright (c) 2026 Guruprasath Annadurai; SPDX-License-Identifier: MIT -->
# Phase 4 launch acceptance checklist

This checklist is not deployment approval. Phase 3 qualified base:
`9a721aa078daba5d554120d7aeb61d5febcdcc79` (tree
`b2d7f3c27c7044be38dc261d5e00ede0a8cb9b9c`). No cloud mutation is authorized.
All unexecuted items remain PENDING, not PASS. Antigravity qualification is
independent website engineering review, not SOC 2/ISO certification or a
commercial penetration test.

| Stage | Item | Owner | Required evidence | State |
|---|---|---|---|---|
| PRE-DEPLOY | Exact-head repository CI, artifact hashes and clean tree | Codex | Eight workflows; nine main jobs; accepted Codecov upload | PENDING |
| PRE-DEPLOY | Independent Phase 4 qualification | Antigravity | Exact SHA/tree independent report | PENDING |
| OWNER INPUT | Security/legal/support/commercial/package decisions | Founder + counsel where relevant | Approved register below | OPEN |
| DEPLOY | Domain control and deployment approval | Founder | Explicit approval identifying artifact manifest | OPEN |
| DEPLOY | Full (strict) TLS, origin protection and routing | Infrastructure owner | Config export and certificate verification | OPEN |
| DEPLOY | Versioned asset retention and atomic HTML activation | Infrastructure owner | Deployment record with old/new manifest | OPEN |
| POST-DEPLOY | Read-only live smoke | Website verifier | Explicit BASE_URL report; TLS/DNS/headers/routes/assets | PENDING |
| POST-DEPLOY | Browser/no-JS/privacy/accessibility qualification | Independent verifier | Actual deployment browser evidence, not local preview | PENDING |
| ROLLBACK | Prior artifact availability and restore rehearsal | Infrastructure owner | Prior manifest and routing recovery evidence | PENDING |
| EXTERNAL GATE | Production product and package release | Product release owner | Separate runtime/release/security gates | OPEN |

## Owner-input register

| Input | Owner | Evidence required | State |
|---|---|---|---|
| OFFICIAL_SECURITY_CONTACT_REQUIRED | Founder | Approved monitored URI and contact operation | OPEN |
| LEGAL_ENTITY | Founder/counsel | Approved entity identity | OPEN |
| REGISTERED_ADDRESS | Counsel | Whether legally required; approved address if required | OPEN |
| JURISDICTION | Counsel | Approved legal terms | OPEN |
| SUPPORT_CONTACT | Founder | Verified delivery and truthful support model | OPEN |
| COMMERCIAL_PRICING_OWNER_GATE | Founder | Approved prices, refund mechanics, SLA/support scope | OPEN |
| BILLING_PROVIDER | Founder | Approved commercial activation | OPEN |
| PACKAGE_IDENTITY_OWNER_GATE | Founder | Distribution strategy and actual publication evidence | OPEN |
| PRODUCTION_DOMAIN_CONTROL | Founder | Domain ownership/control confirmation | OPEN |
| PRODUCTION_DEPLOY_AUTHORITY | Founder | Explicit deployment approval | OPEN |

## Engineering / external blocker separation

P0/P1/P2/P3 engineering counts are determined from fresh validation, not this
template. Do not convert OPEN owner or external gates into invented engineering
passes. No final readiness verdict until exact-head CI and independent review.
Cloud provisioning, legal approval, billing activation, package publication and
certification are outside Codex website ownership.
