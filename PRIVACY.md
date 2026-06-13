# Privacy guarantees

This document describes the differential privacy properties of PrivacyLabel, the threat model it operates under, and the budget accounting model.

---

## What differential privacy means here

Differential privacy (DP) is a mathematical framework for releasing information about a dataset while protecting the privacy of individual records. A randomised algorithm `M` is (ε, δ)-DP if for any two datasets `D` and `D'` that differ in exactly one record, and any output set `S`:

```
Pr[M(D) ∈ S] ≤ exp(ε) × Pr[M(D') ∈ S] + δ
```

Informally: the output of `M` is nearly the same whether or not any single individual's record is included. An adversary who sees the output cannot confidently infer whether a specific person contributed to the dataset.

In PrivacyLabel, the output that leaves the device is the privatised gradient vector. The guarantee applies to that vector: an observer who intercepts the gradient submission cannot determine whether any specific record from the local JSONL file contributed to it.

---

## Mechanism parameters

| Mechanism | Type | Noise scale |
|---|---|---|
| Laplace | (ε, 0)-DP | `scale = sensitivity / ε` |
| Gaussian | (ε, δ)-DP | `σ = √(2 ln(1.25/δ)) × sensitivity / ε` |
| Exponential | (ε, 0)-DP | `P(i) ∝ exp(ε × score_i / (2 × sensitivity))` |
| DP-SGD (gradient privatisation) | (ε, δ)-DP | Gaussian with `sensitivity = gradient_clip` |

The Gaussian sigma formula is the standard analytic calibration from Dwork & Roth (2014). It is a slight overestimate relative to the tighter numerical accountant, which means the actual privacy cost is at most as stated — the guarantee is conservative.

---

## Default parameter choices

The default `FederatedClient` parameters are:

```python
epsilon_per_round = 0.1   # per-round privacy cost
total_epsilon     = 1.0   # lifetime budget (10 rounds)
delta             = 1e-6  # failure probability
gradient_clip     = 1.0   # L2 sensitivity bound
```

**Choosing ε:** Lower ε means more noise and stronger privacy but lower gradient quality. `ε = 0.1` per round is a moderately strong setting. For highly sensitive data (medical records, financial transactions), values in the 0.01–0.1 range are common in the literature. For less sensitive data where utility matters more, 0.5–1.0 is reasonable.

**Choosing δ:** The failure probability δ should be much smaller than `1/n` where `n` is the dataset size. `δ = 1e-6` is appropriate for datasets up to millions of records.

**Choosing gradient_clip:** This sets the L2 sensitivity bound. Gradients with larger norm are clipped to this value before noise is added. A value of 1.0 is a standard starting point; tuning this to match the actual gradient magnitudes in your setting will improve utility.

---

## Budget accounting

PrivacyLabel uses **basic (sequential) composition**. If you run `k` rounds each costing `(ε_r, δ_r)`, the total cost is at most `(k × ε_r, k × δ_r)`.

Basic composition is the most conservative bound. Tighter alternatives include:
- **Moments accountant / Rényi DP** — used by TensorFlow Privacy, typically allows 2–5× more rounds for the same guarantee
- **Zero-concentrated DP (zCDP)** — intermediate tightness, simpler than the moments accountant
- **f-DP / hockey-stick divergence** — tightest known bound for Gaussian mechanisms

The `PrivacyBudget` class tracks `spent_epsilon` and `spent_delta` and raises `PrivacyBudgetExhaustedError` before any operation that would exceed the configured budget. This makes it impossible to accidentally overspend — the error is raised on the `train_round()` call before any data is loaded or any model is called.

---

## Threat model

**What PrivacyLabel protects against:**

- A compromised or honest-but-curious aggregation server that logs all submitted gradient updates.
- A network adversary that intercepts gradient submissions in transit.
- Post-hoc reconstruction attacks against the gradient vectors stored by the aggregator.

**What PrivacyLabel does not protect against:**

- A fully compromised edge device (if the device is compromised, the raw data is accessible directly).
- Membership inference attacks against the LLM itself (if you use an external API, that API sees the text). For full on-device privacy, use a local model only.
- Re-identification via the label distribution in the `RoundSummary` — the summary includes aggregate statistics (num_labels, mean_confidence) that could in principle reveal aggregate properties. These statistics do not have DP guarantees by default.
- Byzantine attacks where a malicious node submits crafted gradients. The `byzantine_robust=True` flag (Weiszfeld geometric median) provides robustness against up to ~49% Byzantine nodes, but this is a Byzantine fault tolerance mechanism, not a privacy mechanism.

---

## Data residency

The `FederatedClient._load_local_data()` method reads from a local path and returns the records in memory. Those records are:

1. Passed to `provider.batch_label()` — if your provider is an external API (OpenAI, Anthropic), the text is sent to that API. Use a local provider (Ollama, HuggingFace) if the text must remain on-device.
2. Never serialised to disk by PrivacyLabel.
3. Never included in the `NodeUpdate` submitted to the aggregator (the update contains only the privatised gradient vector, node ID, sample count, and round number).
4. Garbage-collected after `train_round()` returns.

The `RoundSummary` returned to the caller contains no raw text or labels. It contains only aggregate statistics: sample count, label count, mean confidence, gradient L2 norm, and privacy budget consumption.

---

## Audit trail

Every `RoundSummary` includes a `timestamp` (UTC ISO 8601) and the cumulative `privacy_spent` dictionary. Logging these summaries provides an audit trail of budget consumption per node per round without exposing any sensitive data:

```json
{
  "node_id": "hospital-node-01",
  "round_number": 3,
  "num_samples": 150,
  "num_labels": 150,
  "mean_confidence": 0.8921,
  "gradient_norm": 0.3142,
  "privacy_spent": {
    "epsilon": 1.0,
    "spent_epsilon": 0.3,
    "delta": 1e-06,
    "spent_delta": 3e-06,
    "remaining_epsilon": 0.7,
    "is_exhausted": false
  },
  "timestamp": "2026-06-13T10:42:17.831Z"
}
```

---

## References

- Dwork, C. and Roth, A. (2014). *The Algorithmic Foundations of Differential Privacy.* Foundations and Trends in Theoretical Computer Science.
- Abadi, M. et al. (2016). *Deep Learning with Differential Privacy.* ACM CCS.
- McMahan, H. B. et al. (2017). *Communication-Efficient Learning of Deep Networks from Decentralized Data* (FedAvg). AISTATS.
- Blanchard, P. et al. (2017). *Machine Learning with Adversaries: Byzantine Tolerant Gradient Descent* (geometric median / Krum). NeurIPS.
