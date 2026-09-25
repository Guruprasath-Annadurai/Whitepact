# WhitePact Formula — Proof Obligations v0.1

Hard obligations are **boolean** (or three-valued with UNKNOWN blocking EXECUTE). No weighted average substitutes for failure.

---

## Obligation taxonomy

| Kind | Satisfied when | UNKNOWN blocks EXECUTE? |
|------|----------------|-------------------------|
| HARD | Deterministic or trusted attestation | Yes, if applicable |
| SOFT | Policy advisory | No (may elevate to APPROVAL) |
| FUTURE | Bounded model check | Yes if mandatory class |

---

## Hard obligations (PO-*)

### PO-IDENTITY

| | |
|--|--|
| **Claim** | Actor `σ` is authenticated and tenant-bound |
| **Domain** | `(σ, tenant_id, session)` |
| **Failure** | Spoofed principal → DENY |
| **Applicability** | All side-effecting actions |

### PO-AUTHORITY

| | |
|--|--|
| **Claim** | `Authorized(σ, α, ρ, ctx, t)` |
| **Failure** | Missing/expired grant → DENY / REAUTHORIZE |
| **Applicability** | All EXECUTE paths |

### PO-PURPOSE

| | |
|--|--|
| **Claim** | Declared purpose matches grant purpose constraint |
| **Failure** | Purpose mismatch → DENY |
| **Applicability** | Grants with purpose binding |

### PO-POLICY

| | |
|--|--|
| **Claim** | `P_t` permits `α` in `ctx` |
| **Failure** | Deny rule → DENY |
| **Applicability** | All |

### PO-GRANT

| | |
|--|--|
| **Claim** | Grant `g` is `Valid(g,t)`, not revoked/consumed |
| **Failure** | Lifecycle → DENY |
| **Applicability** | Grant-based auth |

### PO-TEMPORAL

| | |
|--|--|
| **Claim** | `t ∈ [t_start, t_end)` and ordering constraints |
| **Failure** | Expired mid-plan → DENY / REAUTHORIZE |
| **Applicability** | Time-bounded grants |

### PO-TRUST

| | |
|--|--|
| **Claim** | `TrustSatisfied(α)` — no required UNKNOWN |
| **Failure** | UNKNOWN → ¬EXECUTE |
| **Applicability** | Trust-gated channels |

### PO-CAPABILITY

| | |
|--|--|
| **Claim** | Effects of `α` ⊆ `𝒞_adm` (as modeled) |
| **Failure** | Latent escalation → REAUTHORIZE / DENY |
| **Applicability** | Tooling actions |
| **Note** | Incomplete closure → UNKNOWN obligation |

### PO-REPLAY

| | |
|--|--|
| **Claim** | Idempotency key / nonce valid; no duplicate side effect |
| **Failure** | Replay → DENY |
| **Applicability** | Non-idempotent externals |

### PO-TENANT

| | |
|--|--|
| **Claim** | Resources in tenant boundary |
| **Failure** | Cross-tenant → DENY |
| **Applicability** | All |

### PO-RISK

| | |
|--|--|
| **Claim** | `ResidualRisk(α) ≤ risk_ceil` |
| **Failure** | Exceed → APPROVAL / DENY per policy |
| **Applicability** | Risk-classified actions |

### PO-EVIDENCE

| | |
|--|--|
| **Claim** | Required evidence present, fresh, verified |
| **Failure** | Missing → UNKNOWN / APPROVAL |
| **Applicability** | Regulated / irreversible |

### PO-FUTURE-BOUND

| | |
|--|--|
| **Claim** | `F_H(W,α) ⊆ SFE_H(W)` under declared abstraction soundness |
| **Failure** | Modeled violation → DENY / SANDBOX |
| **Applicability** | Mandatory future-check classes |
| **Qualified** | “No violation **in bounded model**” |

---

## Applicability matrix (excerpt)

| Action class | PO-IDENTITY | PO-AUTHORITY | PO-FUTURE-BOUND | PO-REPLAY |
|--------------|-------------|--------------|-----------------|-----------|
| Read public | ✓ | optional | optional | — |
| Write DB | ✓ | ✓ | ✓ | ✓ |
| External API | ✓ | ✓ | ✓ | ✓ |
| Simulate only | ✓ | soft | optional | — |

Full matrix is policy-bound at `PolicyVersion`.

---

## Formal judgment shape

```text
AllowExecute(α) ≡
  ∀ p ∈ HardObligations(α): status(p) = SATISFIED
  ∧ (FutureMandatory(α) → FutureCondition(α))
  ∧ ResidualRiskWithinPolicy(α)
  ∧ NoKnownAuthorityViolation(α)
```

`FutureCondition(α)` documentation string must include: `H`, abstraction type, graph completeness, search budget outcome.

---

## Proof object field normativity

| Field | Normative |
|-------|-----------|
| `formula_version`, `formula_spec_hash` | Yes |
| `proof_obligations`, `satisfied_*`, `failed_*`, `unknown_*` | Yes |
| `capability_paths`, `causal_paths` | Informative |
| `future_search_summary` | Informative (must state INCOMPLETE) |
| `uncertainty` | Informative |
| `reason_codes` | Yes |
| `evidence_hash` | Yes |

---

## Gate 1 boundary

No runtime verifier implements these obligations yet. V1.3.1 enforcement paths remain unchanged.
