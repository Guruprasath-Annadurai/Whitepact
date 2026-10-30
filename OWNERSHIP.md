# Ownership and contributor identity

Founder declaration dated 29 October 2026: WhitePact is the solo-owned project
of Guruprasath Annadurai. Techezz Infos is not an authorized contributor,
owner, partner or representative. This records the founder's current declaration;
it does not independently establish who authored any historical change.

The approved identity for future founder-authorized contributions is:

`Guruprasath Annadurai <annaduraiguruprasath7@gmail.com>`

Use repository-local Git configuration, never a copied identity from another
project. Other identities, including automated accounts, require explicit
verification and contribution authorization before new submissions. A name,
email, GitHub account association or matching trailer alone proves neither
authorship nor submission rights.

Before a new contribution, run `scripts/engineering/verify_contributor_identity.py`
with the explicit reviewed base and head commit SHAs. It rejects unauthorized
author/committer metadata and missing founder signoff in the introduced range.
The check never changes commits or adds a signoff. It is an additional local
pre-publication check; existing hosted DCO checks remain mandatory. It is not a
server-side prevention mechanism unless separately integrated and qualified.

Only use `git commit -s` after the founder personally authorizes that specific
contribution and accepts the DCO obligations. General ownership and Git identity
configuration are not standing consent to sign every future patch.

Historical Git metadata and dated evidence are preserved verbatim for audit.
Their recorded names do not grant present project authority. Old resume/setup
instructions prescribing a different identity are superseded by this policy.
Do not execute historical identity instructions, silently replace historical
authors, add a mailmap implying unproved equivalence, or backdate declarations.

The unsigned historical commit `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc`
remains blocked under the existing DCO gate. Ownership clarification does not
repair its trailer. Any clean-lineage migration requires separate founder,
security and independent review of rights, provenance, policy and requalification;
no migration or exception is authorized by this document.

For new projects, verify their own identities and authorizations. Never import
WhitePact's historical attribution, Git configuration or DCO declarations.
