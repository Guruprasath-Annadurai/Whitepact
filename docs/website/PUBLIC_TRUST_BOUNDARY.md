# Public trust boundary — editorial source of truth

WhitePact is an independent pre-execution runtime authorization boundary for
autonomous AI agents on supported, configured integration paths.

> The agent may think freely. It may plan freely. But it cannot act outside independently enforced authority.

Authentication identifies a principal. It does not itself establish action
authority. Intent, consent, authority, applicable policy/risk/approval and the
current authorization state must be evaluated by the configured service/runtime,
not inferred in browser code or from a paid subscription.

Evaluation output is not enforcement by itself. Consequential effects must travel
through the supported guarded execution boundary. Arbitrary tool/plugin code
inside the trusted process, direct calls outside configured integration paths,
or compromised operators/infrastructure are not universally controlled by a
public website or a Python configuration flag. Deployment/TCB boundaries must
be qualified for each integration; do not claim universal non-bypassability.

The website control-chain diagram is a conceptual map: Constitution → Identity →
Authority → Intent → Policy → Capability Graph → Risk → Approval → Judgment →
Short-Lived Execution Grant → Isolated Execution → Evidence → Audit → Revocation.
It is not an assertion that every adapter invokes every named subsystem, that
every deployment offers container isolation, or that queued dispatcher work is
enabled. Current product contracts and supported deployment configuration govern.

Authorization/grants are scoped and time-bound where implemented. Approval does
not mint authority in the browser. Revocation blocks subsequent checks on the
supported path; it cannot retroactively reverse a completed external effect.
UNKNOWN must remain UNKNOWN. An HTTP success, redirect or missing evidence does
not prove a downstream action or payment completed. Reconcile before any retry.

Hash-chained records are tamper evidence with documented verifier/storage
boundaries, not an immutable ledger against a fully compromised database.
Evidence is not authority and does not independently prove an external effect.

Implementation, public deployment, commercial availability and external
certification are separate facts. No SOC 2/ISO certification, universal safety,
independent pentest or uptime guarantee is introduced by this phase.
