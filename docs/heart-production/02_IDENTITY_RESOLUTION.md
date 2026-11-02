# Real Principal / Identity Resolution (Phase 2)

> Connects the Heart's root-authority vocabulary to WhitePact's real,
> already-live authentication mechanisms — without inventing a new
> authentication system and without conflating authentication with
> authority.

## What already exists (reused, not rebuilt)

Per `00_CURRENT_RUNTIME_MAP.md` §2, three real credential sources
already authenticate a caller in production:

- **Static API key** — `db/org_repository.py` `OrgRepository.authenticate()`
- **OIDC JWT** — `auth/oidc.py` `OIDCProvider.validate_token()`
- **VC-JWT bearer** — `auth/verifiable_credential.py` `VerifiableCredentialProvider.validate_presentation()`

Each already produces a real `IdentityContext` (`governance/models.py`)
or `PrincipalClaim` (`governance/principal.py`, the VC path). This
phase does not touch any of these — no new authentication system, per
the master prompt's own rule.

## The separation this phase keeps explicit

> Authentication: "Who/what is this?"
> Heart: "What legitimate authority does this identity possess here?"

A successfully authenticated identity must not automatically have
authority. `governance/identity_authority_adapter.py` enforces this by
construction: it only ever produces a `RootAuthorityRecord` — the
Heart's own *claim* about who a root is — never anything resembling a
grant of authority. Whether that claim is actually legitimate is
`root_authority.validate_root_chain()`'s question (H3), not this
adapter's, and `validate_root_chain()` requires either a terminal
`RootType` or a resolvable `authority_source` chain — this adapter
alone can never make a non-terminal identity pass.

## The mapping, and why it's conservative

| `IdentityContext.kind` | `RootType` | Terminal? | Reasoning |
|---|---|---|---|
| `"human"` | `HUMAN` | Yes | Explicit human kind |
| `"api_key"` | `ORGANIZATION` | Yes | Org-admin-provisioned credential (`00_CURRENT_RUNTIME_MAP.md` §12) |
| `"oidc"` | `WORKLOAD_IDENTITY` | No | **Ambiguous** — today's `IdentityContext.from_org_context()` sets `kind="oidc"` for both human SSO and machine client-credentials tokens, with no discriminator. Fail-safe: treat as non-terminal |
| `"vc"` | `SERVICE_PRINCIPAL` | No | Verified-principal path — never human by construction |
| `"agent"` | `SERVICE_PRINCIPAL` | No | Agent identity — machines cannot originate authority (constitutional law H2) |
| `"workload"` | `WORKLOAD_IDENTITY` | No | Explicit workload kind |
| *(unrecognized)* | `WORKLOAD_IDENTITY` | No | Fail-safe default for any future kind |

The asymmetry that motivates the conservative choice for `"oidc"`:
misclassifying a genuinely human-controlled OIDC token as non-terminal
costs *availability* (a deny until Phase 5 supplies a real source);
misclassifying a machine-controlled one as `HUMAN`/terminal would let
authority originate where it constitutionally cannot. The safe
direction was chosen.

## The `PrincipalClaim` (VC) path

`PrincipalClaim` (`governance/principal.py`, Authority Everywhere
Phase 3) already carries `issuer`/`credential_type` directly from a
real verification event — more precise than routing through the
generic `IdentityContext` mapping. Always maps to `SERVICE_PRINCIPAL`;
both `holder_kind` values (`"service_account"`, `"external_agent"`)
are non-human by construction, so unlike `"oidc"` this is not a
judgment call.

## What this phase does not do

- Does not resolve a real `authority_source` chain (Phase 5).
- Does not persist anything (Phase 3).
- Does not wire this adapter into `apply_governance()`/
  `apply_upstream_governance()` (Phase 6).
- Does not add a fourth authentication mechanism.

## Verification

19 tests in `tests/test_identity_authority_adapter.py`: every kind's
mapping individually, the fail-safe default for unrecognized kinds,
that a terminal record validates immediately with no resolver, that a
non-terminal record fails closed (`ROOT_TYPE_CANNOT_SELF_ORIGINATE`)
without a source and validates once one is supplied, the
`PrincipalClaim` path for both `holder_kind` values, plus 4 Hypothesis
property tests confirming the terminal/non-terminal partition holds
for every known kind and for arbitrary unknown ones.
