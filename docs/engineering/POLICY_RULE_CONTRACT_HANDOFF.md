# Ordered policy rule contract gap — Antigravity ownership

The API `PolicyRuleCreateRequest` permits all five canonical governance decision
names, while `PolicyRule.__post_init__` only accepts ALLOW, REQUIRE_APPROVAL and
DENY. Actual constructor execution rejects ALLOW_WITH_REDACTION and QUARANTINE.
This is unchanged in the read-only Antigravity reference b3a88396.

The console previously offered QUARANTINE creation. It now offers only the three
supported ordered-rule effects and explains the limitation. Runtime responses
retain all five canonical decisions; this is not a change to authority semantics.

M11 correction: `web_add_policy_rule` already catches the constructor's ValueError
and returns HTTP 422. Fresh actual TCP/PostgreSQL tests reject both unsupported
effects and verify policy is unchanged. The previous recommendation to introduce
a safe validation error was unnecessary; no unhandled-500 or authorization bypass
is established by this difference. Request-model validation could be narrowed for
clarity by the Core owner, but is not a demonstrated security blocker.

Do not add redaction/quarantine semantics to ordered rules merely to satisfy the UI.
Runtime decision classification remains distinct and unchanged. Tiered change,
step-up and second-reviewer ceremonies still need a reviewed customer integration.

The current UI regression proves offered choices, not backend authorization.
