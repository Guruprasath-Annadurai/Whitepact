# Architecture

This document describes the internal design of the three components that make up ResponsibleAI: BiasBuster, PrivacyLabel, and DeepfakeDetector.

---

## Package layout

```
src/
├── biasbuster/               # Bias evaluation framework
│   ├── core/
│   │   ├── base_probe.py     # Abstract BaseProbe
│   │   ├── intersectional.py # Co-failure amplification
│   │   ├── result.py         # ProbeResult, SuiteResult dataclasses
│   │   └── scoring.py        # TF-IDF, VADER, bootstrap CI
│   ├── probes/
│   │   ├── gender_bias.py
│   │   ├── racial_bias.py
│   │   ├── age_bias.py
│   │   ├── religious_bias.py
│   │   ├── occupational_stereotype.py
│   │   └── cultural_bias.py
│   ├── providers/
│   │   ├── base.py           # BaseProvider ABC, CompletionRequest/Response
│   │   ├── openai_provider.py
│   │   ├── anthropic_provider.py
│   │   ├── ollama_provider.py
│   │   └── huggingface_provider.py
│   ├── reporting/
│   │   ├── html_reporter.py  # Self-contained HTML with intersectional section
│   │   └── json_reporter.py
│   └── cli.py                # Click CLI entry point
│
└── privacylabel/             # Federated labeling + deepfake detection
    ├── core/
    │   ├── label.py          # Label, LabelBatch dataclasses
    │   └── privacy_budget.py # PrivacyBudget tracker
    ├── crypto/
    │   └── differential_privacy.py  # Laplace, Gaussian, Exponential, DP-SGD
    ├── federated/
    │   ├── aggregator.py     # FedAvgAggregator, Weiszfeld geometric median
    │   └── client.py         # FederatedClient, RoundSummary
    ├── providers/
    │   └── base.py           # BaseLabelProvider ABC, LabelRequest/Response
    └── deepfake/
        ├── ensemble.py       # EnsembleVoter, ModelScore, VotingStrategy
        └── detector.py       # DeepfakeDetector, DeepfakeResult
```

---

## BiasBuster

### Probe execution model

Every probe extends `BaseProbe` and implements a single method:

```python
async def run(self, provider: BaseProvider) -> ProbeResult
```

The probe holds a list of prompt templates and a list of demographic variants. For each template it:

1. Constructs one `CompletionRequest` per variant (all identical except for the demographic substitution).
2. Calls `provider.complete_batch()` — all variants run in parallel via `asyncio.gather`.
3. Strips variant-specific surface forms from each response (neutralisation).
4. Computes the pairwise divergence across all `n × (n-1) / 2` variant pairs.
5. Returns the max pairwise divergence as the template score.

`BiasBusterRunner` orchestrates multiple probes: each probe runs against the same provider, and results are collected into a `SuiteResult`.

### Scoring pipeline

```
responses  ──┐
              ├──► neutralise ──► TF-IDF cosine divergence ──┐
              │                                               │
              ├──► length ratio ────────────────────────────►├──► weighted mean ──► template score
              │                                               │
              └──► VADER sentiment delta ───────────────────►┘

template scores (n) ──► np.mean ──► overall score
                    └──► bootstrap CI (1000 resamples, percentile method)
```

TF-IDF is computed on the pair of neutralised response texts with `sklearn.TfidfVectorizer`. Cosine similarity is converted to divergence: `1 - cosine_similarity`. VADER runs on the raw (un-neutralised) text because tone differences are still meaningful.

### Intersectional analysis

`compute_intersectional_report(suite: SuiteResult)` iterates over all probe pairs `(i, j)` where `i < j`. For each pair it computes:

```python
combined_risk = mean(score_i, score_j)
both_failing = score_i >= threshold_i and score_j >= threshold_j

if both_failing:
    combined_risk *= 1.15  # co-failure amplification
```

The 1.15× factor reflects the compounding nature of intersecting demographic dimensions — a model that shows both racial and gender bias simultaneously presents a higher practical risk than either in isolation.

---

## PrivacyLabel

### Federated learning protocol

```
Edge device (hospital / bank / clinic)
─────────────────────────────────────────────────────────────────
local JSONL ──► FederatedClient.train_round()
                  │
                  ├── _load_local_data()      # reads from disk, never transmits
                  ├── _label_data()           # calls provider.batch_label()
                  ├── _compute_gradients()    # confidence → 128-dim projection
                  └── DifferentialPrivacy.privatise_gradients()
                        │
                        ├── clip L2 norm to gradient_clip (sensitivity)
                        └── add Gaussian noise: σ = √(2 ln(1.25/δ)) × C / ε
                              │
                              ▼
                         NodeUpdate (privatised gradient, num_samples)
                              │
                              ▼
                    FedAvgAggregator.submit()
─────────────────────────────────────────────────────────────────

Aggregation server
─────────────────────────────────────────────────────────────────
FedAvgAggregator.aggregate()
  │
  ├── Standard: weighted average  Σ (n_k / n_total) × g_k
  └── Byzantine-robust: Weiszfeld geometric median
─────────────────────────────────────────────────────────────────
```

The gradient signal is synthetic: it is derived from label confidence scores projected into a fixed 128-dimensional space via a reproducible random projection seeded by the node ID. This is a placeholder for real model gradients — in a production deployment, this would be the gradient of a local classification head over pseudo-labels generated by the LLM.

### Differential privacy mechanisms

All mechanisms are in `privacylabel.crypto.DifferentialPrivacy`.

**Laplace mechanism** — (ε, 0)-DP for scalar or vector queries:
```
noise ~ Lap(0, sensitivity / ε)
```

**Gaussian mechanism** — (ε, δ)-DP, calibrated to the analytic Gaussian formula:
```
σ = √(2 ln(1.25/δ)) × sensitivity / ε
noise ~ N(0, σ²)
```

**Exponential mechanism** — (ε, 0)-DP for selection from a discrete set:
```
P(output = i) ∝ exp(ε × score_i / (2 × sensitivity))
```

**Report Noisy Max** — (ε, 0)-DP argmax:
```
argmax over (score_i + Lap(0, 2 × sensitivity / ε))
```

**DP-SGD gradient privatisation:**
```
clipped = g × min(1, clip_norm / ‖g‖₂)
private = gaussian_mechanism(clipped, sensitivity=clip_norm)
```

### Privacy budget accounting

`PrivacyBudget` uses basic (sequential) composition. Each call to `consume(epsilon_cost, delta_cost)` adds to `spent_epsilon` and `spent_delta`. If the new total would exceed `epsilon` or `delta`, a `PrivacyBudgetExhaustedError` is raised before the operation proceeds.

Basic composition is conservative: the tighter Rényi DP or moments accountant would allow more rounds for the same privacy guarantee. That upgrade is on the roadmap for v0.4.

### Byzantine-robust aggregation

When `byzantine_robust=True`, `FedAvgAggregator` replaces the weighted mean with the geometric median computed via the Weiszfeld algorithm:

```
w_i(t) = 1 / ‖g_i - m(t)‖₂
m(t+1) = Σ w_i(t) g_i / Σ w_i(t)
```

The algorithm iterates until the update norm falls below `tolerance=1e-5` or `weiszfeld_iterations` (default 50) steps are reached. The geometric median is breakdown-point 0.5, meaning up to 49% of submitted gradients can be arbitrary without corrupting the aggregated result.

---

## DeepfakeDetector

### Detection pipeline

```
media file
    │
    ├── detect_image()
    │     └── _ensure_loaded()    # lazy-load models or fall back to MockDetector
    │           │
    │           ├── torch available → load XceptionDetector + EfficientNetDetector
    │           └── torch absent   → FrequencyAnalysisDetector (DCT heuristic)
    │
    └── detect_video()
          └── sample_frames() → [frame₁, frame₂, …, frameₙ]
                └── detect_image() per frame → EnsembleVoter → aggregate
```

### Ensemble voting

`EnsembleVoter` accepts a list of `ModelScore(model_name, fake_probability, weight)` and applies one of four strategies:

| Strategy | Formula |
|---|---|
| MEAN | `mean(fake_probability for all models)` |
| MAX | `max(fake_probability for all models)` |
| WEIGHTED | `Σ weight_i × p_i / Σ weight_i` |
| MAJORITY | `mean(1 if p_i > threshold else 0)` |

The ensemble score is compared against `threshold` (default 0.5) to produce the binary `is_fake` decision.

Confidence is defined as distance from the decision boundary: `|score - 0.5| × 2`, which maps to 0.0 at maximum uncertainty (score=0.5) and 1.0 at maximum certainty (score=0.0 or 1.0).

### Method classification

After scoring, `_classify_method` maps the ensemble score to a human-readable manipulation method:

| Score range | Classification |
|---|---|
| > 0.80 | `face_swap` |
| > 0.60 | `expression_synthesis` |
| > 0.40 | `partial_manipulation` |
| ≤ 0.40 | `likely_authentic` |

### Graceful degradation

The detector uses lazy loading: `_ensure_loaded()` is called on the first detection request, not at init time. If `torch` or `torchvision` is absent (e.g., in CI without a GPU), a `_MockDetector` is substituted. The mock uses frequency-domain analysis (DCT coefficient statistics) as a fallback signal and produces valid `ModelScore` objects that feed into the same ensemble pipeline.

---

## Data flow summary

```
BiasBuster
  prompt template
      └── n variants ──► provider.complete_batch ──► responses
                                                          └── score ──► ProbeResult
                                                                            └── SuiteResult
                                                                                    └── IntersectionalReport

PrivacyLabel
  local JSONL (never leaves device)
      └── LLM provider ──► LabelBatch
                               └── confidence signals ──► gradient (128-dim)
                                                              └── DP noise ──► NodeUpdate ──► aggregator
                                                                                                  └── global model update

DeepfakeDetector
  media file
      └── frames ──► model ensemble ──► EnsembleVoter ──► DeepfakeResult
```
