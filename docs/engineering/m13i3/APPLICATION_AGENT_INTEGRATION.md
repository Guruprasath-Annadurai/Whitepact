# Application, agent and recorded authority integration

New `readCustomerAuthorityRecords` consumes the existing authenticated owner/admin GET `/api/enterprise/organizations/{organization}/authority/status`. Backend `AuthorityService.get_authority_status` binds the actor's tenant and returns latest unrevoked root plus a paired consent projection. This read contract is distinct from effective authorization.

New `AuthorityRecordDetails` appears within Agents, opt-in only. It projects known root/consent IDs, recorded subject/issuer/type/method/timestamps/digests and consent scope/purpose/targets. It validates tenant, pair presence, field types, timestamps and digest shape. Unexpected fields are discarded. Only the first10 of each returned scope list render, with the returned count and explicit bounded-preview label. Raw targets render as text, not executable links.

Loading, absent records, malformed/foreign data,401,403,503, explicit retry, stale refresh, cancellation and tenant switching have distinct conservative behavior. No prior consent remains visible as current after a failed refresh. Recorded expiry/digest/scope is not verified permission; no signing, grant or mutation control is added.

Fresh frontend validation:301tests/32files passed, including12 new records tests; lint/type/build passed. Browser fixture validation is reported separately.

Application ownership/association/capability contracts in Argon remain unqualified and are not imported. Existing agent inventory and organization reads remain active; rename stays disabled pending atomic expected-workspace/version backend support. Policies, approvals and evidence retain existing supported consumers. Incident/recovery/delegation authority paths remain gated where no independent contract qualifies.
