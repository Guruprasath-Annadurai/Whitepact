# M13-I1 backend contract disposition

| Requirement | Actual inspected contract | Disposition |
| --- | --- | --- |
| Application inventory and ownership | No application list/create/ownership API in inspected enterprise/router and authority/router; organization ownership/service accounts are different entities | **BLOCKED**, security/product backend owner must define authenticated tenant-scoped application ownership model and routes |
| Executable capability visibility | Agent list supplies registration/lifecycle/reported delegation only; allowed action/target scope on authority/delegation records is not a complete effective-capability enumeration | **BLOCKED**, no client reconstruction or registration-to-authorization inference |
| Agent inventory | Existing tenant-scoped GET, reader validation and product page retained; actual fresh authenticated owner GET succeeds | Supported read-only integration; no new mutation enabled |
| Root/bootstrap status | Existing GET succeeded in actual owner session | Advisory read only; no assertion that owner has execution authority |
| First passkey | Challenge API responds, default expected origin differs from real app origin | **BLOCKED**, handoff to Antigravity; no security source patch |
| Consent/root/delegation/execution | APIs exist, but actual full prerequisite chain is not qualified by the current customer attempt | **BLOCKED**, no mock/seed or cosmetic success substitute |
| Organization selection | Switch endpoint exists, but no new multi-organization customer proof in this run | Retain existing gating; do not expand authority based on a membership label |

Safe product integration already present in the product checkpoint remains intact. This integration adds a reproducible real HTTP attempt and exact-head qualification jobs, rather than inventing missing APIs. Independent cryptographic/service tests and actual browser/HTTP customer authorization are separate evidence. No backend security-kernel enforcement, original reproducer or privileged UI control was changed.
