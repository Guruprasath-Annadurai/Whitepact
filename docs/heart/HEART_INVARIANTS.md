# WhitePact Heart — Invariants Ledger (Phase H14)

> An honest ledger of the security/correctness invariants claimed by
> Heart Phases H1-H13, each paired with the specific test (or tests)
> that verify it. This is **property-based assurance**, not formal
> verification in the TLA+/Coq/model-checker sense — every invariant
> below is checked by Hypothesis-generated inputs across a large space
> of cases, not proven for all possible inputs by a proof assistant.
> Where a claim below has no corresponding test, it is marked
> **UNVERIFIED** rather than silently omitted.

## How to read this ledger

Each row: the invariant, in plain language; the phase that introduced
it; the test(s) that verify it. "Property-tested" means a Hypothesis
`@given`-based test exists specifically for this invariant (not just
an example-based unit test that happens to touch it).

## Root Authority (H3)

| Invariant | Test |
|---|---|
| A chain terminating at HUMAN/ORGANIZATION is always VALID, for any depth | `test_chain_terminating_at_human_or_org_is_always_valid` (property-tested) |
| Any cycle, of any length, is always detected | `test_any_cycle_length_is_always_detected` (property-tested) |
| A non-terminal type with no `authority_source` is never valid | `test_non_terminal_type_with_no_source_is_never_valid` (property-tested) |
| A chain that never reaches a terminal root always terminates (never loops, never falsely VALID) | `test_chain_never_exceeds_max_depth_before_terminating` (property-tested) |
| An intermediate ancestor's temporal state (not type) determines REVOKED/NOT_YET_VALID/EXPIRED | `test_revoked_intermediate_ancestor_invalidates_chain` (regression test for the real bug found in H3) |

## Authority Lattice (H2)

| Invariant | Test |
|---|---|
| `intersect_envelopes()` never produces a result broader than any input | `test_intersecting_result_is_always_legitimate_subset_of_every_input` (property-tested) |
| Hour-window intersection never covers an hour outside either input window | `test_hours_intersection_never_covers_an_hour_outside_either_window` (property-tested; caught a real widening bug on first run) |

## Consent Proof (H4)

| Invariant | Test |
|---|---|
| A fresh proof backed by a valid terminal root is always VALID, for any `ConsentMethod` | `test_fresh_proof_with_valid_terminal_root_is_always_valid` (property-tested) |
| A revoked root never yields a valid consent, regardless of root type | `test_revoked_root_never_yields_valid_consent` (property-tested) |
| A mismatched claimed `root_id` never yields a valid consent | `test_mismatched_root_id_never_yields_valid_consent` (property-tested) |
| Root legitimacy is checked before the proof's own temporal state | `test_root_legitimacy_is_checked_before_temporal_state` |

## Purpose Binding (H5)

| Invariant | Test |
|---|---|
| Matching purpose/refs are always VALID when consent is legitimate, for arbitrary purpose strings | `test_matching_purpose_and_refs_always_valid_when_consent_legitimate` (property-tested) |
| Mismatched purpose strings never yield VALID | `test_mismatched_purpose_strings_never_yield_valid` (property-tested) |
| A `consent_ref` not matching the proof never yields VALID | `test_binding_consent_ref_not_matching_proof_never_yields_valid` (property-tested) |
| Purpose matching is exact-string, never semantic | `test_purpose_matching_is_case_sensitive_exact_string` |

## Delegation Kernel (H6)

| Invariant | Test |
|---|---|
| A legitimate chain with an active delegation is always LEGITIMATE, for arbitrary purpose strings | `test_legitimate_chain_with_active_delegation_always_legitimate` (property-tested) |
| An illegitimate root never yields a legitimate delegation | `test_illegitimate_root_never_yields_legitimate_delegation` (property-tested) |
| **UNVERIFIED**: the referenced root/consent/purpose results actually pertain to the delegation in question | No test — `DelegationRecord` has no cross-reference fields to verify this against (documented limitation, H6) |

## Non-Delegable Authority (H7)

| Invariant | Test |
|---|---|
| Arbitrary combinations of only ordinary action types never violate | `test_any_combination_of_ordinary_actions_never_violates` (property-tested) |
| Any `NON_DELEGABLE` presence always wins regardless of what else is present | `test_any_non_delegable_presence_always_wins_regardless_of_what_else_is_present` (property-tested) |
| `HUMAN_RESERVED` without `NON_DELEGABLE` always reports `HUMAN_RESERVED` | `test_human_reserved_without_non_delegable_always_reports_human_reserved` (property-tested) |

## Authority Lifetime (H8)

| Invariant | Test |
|---|---|
| The age boundary is strict for arbitrary `max_age`/`age` pairs | `test_age_boundary_is_strict` (property-tested) |
| Mismatched digests always yield `STALE_BY_MUTATION` regardless of age | `test_mismatched_digests_always_stale_by_mutation_regardless_of_age` (property-tested) |
| Matching digests never cause mutation-staleness | `test_matching_digests_never_cause_mutation_staleness` (property-tested) |

## Revocation Kernel (H9)

| Invariant | Test |
|---|---|
| An epoch bumped any number of times is always CURRENT against itself | `test_epoch_bumped_n_times_is_current_only_against_itself` (property-tested) |
| Any additional bump after issuance is always `REVOKED_SINCE_ISSUANCE` | `test_any_additional_bump_after_issuance_is_always_revoked` (property-tested) |
| Any org/scope difference always yields `SCOPE_MISMATCH` | `test_any_scope_or_org_difference_always_yields_mismatch` (property-tested) |
| **UNVERIFIED (documented, not fixed)**: `revoke_branch()`'s `revoked_ids` return value is not deduplicated under concurrent calls to the same identity — a real, found, and reported gap | `test_concurrent_revoke_branch_on_the_same_identity_leaves_it_revoked` names this explicitly; the underlying gap is not closed |

## Authority Conflict Resolver (H10)

| Invariant | Test |
|---|---|
| `NON_DELEGABLE` always wins regardless of which other inputs (even entirely legitimate ones) are present | `test_non_delegable_always_wins_when_present_regardless_of_other_inputs` (property-tested) |
| An illegitimate root always blocks when no higher-precedence failure is present | `test_illegitimate_root_always_blocks_when_no_higher_precedence_failure_present` (property-tested) |
| **UNVERIFIED**: the seven composed verdicts all pertain to the same underlying request | No test — this module has no way to detect a caller supplying mismatched objects (documented limitation, H10) |

## Heart Veto (H11)

| Invariant | Test |
|---|---|
| Vetoed if and only if the source `ConflictResolutionResult` was not legitimate | `test_vetoed_iff_not_legitimate` (property-tested) |
| `human_reserved` always preserved regardless of status or its own boolean value | `test_human_reserved_always_preserved_regardless_of_veto_outcome` (property-tested) |
| `enforce_heart_veto()` raises exactly when `is_vetoed` is true | `test_enforce_raises_exactly_when_vetoed` (property-tested) |
| `enforce_heart_veto()` has no override parameter | `test_enforce_has_no_override_parameters` (structural check via `inspect.signature()`, not a docstring claim) |

## Legitimacy Envelope (H12)

| Invariant | Test |
|---|---|
| `is_legitimate` always matches the negation of the wrapped veto's `is_vetoed` | `test_is_legitimate_always_matches_negation_of_vetoed` (property-tested) |
| `explain()`'s `vetoed` field always matches the veto's own `is_vetoed` | `test_explain_vetoed_field_always_matches_veto_is_vetoed` (property-tested) |
| `human_reserved` always passes through to `explain()` | `test_human_reserved_always_passes_through_to_explain` (property-tested) |

## Sovereignty Kernel (H13)

| Invariant | Test |
|---|---|
| A full legitimate chain is always legitimate for arbitrary purpose strings | `test_full_legitimate_chain_always_legitimate_for_arbitrary_purpose` (property-tested) |
| An illegitimate root of either non-terminal type always blocks regardless of other inputs | `test_illegitimate_root_always_blocks_regardless_of_other_inputs` (property-tested) |
| Any number of epoch advances always blocks | `test_any_epoch_advance_always_blocks` (property-tested) |

## Cross-cutting invariants (Phase H14, new)

These span the full H3-H13 chain and were not exercisable by any
single phase's own tests, since each phase composes with at most its
immediate neighbor. Verified in `tests/test_heart_formal_properties.py`.

| Invariant | Test |
|---|---|
| `evaluate()`'s result is always consistent with manually composing `resolve_authority_conflicts()` + `apply_heart_veto()` from the same underlying H3-H9 results | `test_evaluate_is_consistent_with_manual_composition` (property-tested) |
| Adding any single blocking condition to an otherwise-legitimate full chain always flips the result to illegitimate — denial is monotonic, never maskable by additional legitimate inputs | `test_any_single_blocking_condition_added_to_legitimate_chain_always_denies` (property-tested) |
| Every canonical-digest function (root, consent, purpose binding, legitimacy envelope, constitution) is sensitive to every one of its own input fields — no field is silently excluded from the digest | `test_digest_is_sensitive_to_every_field` (parametrized across all five digest functions and every one of their fields) |
| `is_legitimate` is a pure function of the supplied verdicts — identical verdict inputs always produce identical `is_legitimate`, independent of the non-deterministic identity fields (`envelope_id`, `issued_at`, `canonical_digest`) that differ on every call | `test_is_legitimate_is_pure_given_identical_verdicts` (property-tested) |

## What Phase H14 explicitly does NOT claim

- **No formal proof.** Nothing here is machine-checked against *all*
  possible inputs the way a TLA+ spec or a Coq proof would be — every
  property test above samples a large but finite space of generated
  inputs (Hypothesis's default of 100 examples per property, unless
  otherwise configured). A property holding across every sampled case
  is strong evidence, not a proof.
- **No cross-reference verification.** The two `UNVERIFIED` rows above
  (H6, H10) are real, both already documented at the phase level that
  introduced them, repeated here for visibility in one place rather
  than left scattered across individual phase docs.
- **No live-path coverage.** Every invariant above is verified against
  the Heart modules in isolation or composed via `evaluate()` — none
  of it has been exercised against `WhitePactRuntimeGateway.evaluate()`
  or any other production decision path, since nothing wires the Heart
  into either yet (Phase H13's own remaining risk, still true here).
