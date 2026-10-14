# Ordered policy rule contract gap — Antigravity ownership

The API `PolicyRuleCreateRequest` permits all five canonical governance decision
names, while `PolicyRule.__post_init__` only accepts ALLOW, REQUIRE_APPROVAL and
DENY. Actual constructor execution rejects ALLOW_WITH_REDACTION and QUARANTINE.
This is unchanged in the read-only Antigravity reference b3a88396.

The console previously offered QUARANTINE creation. It now offers only the three
supported ordered-rule effects and explains the limitation. Runtime responses
retain all five canonical decisions; this is not a change to authority semantics.

Backend contract required: align API validation with the actual rule constructor
and return a documented safe validation error for unsupported ordered-rule effects.
Do not add redaction/quarantine semantics to ordered rules merely to satisfy the UI.
Add endpoint negative tests for both rejected effects and preserve runtime decision
classification tests. Backend changes remain with Antigravity, not this branch.

The current UI regression proves offered choices, not backend authorization.
