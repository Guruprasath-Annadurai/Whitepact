# Module support classification

Statuses: **CORE** (the authorization kernel; independent verification pending),
**BETA**, **EXPERIMENTAL**, **DEPRECATED**, **UNSUPPORTED**. Nothing here is rated STABLE:
that status requires an independent audit of the exact release tree, which has not happened.

| Module | Status | What it actually does | Must not be used as |
| --- | --- | --- | --- |
| `responsibleai.governance` (gateway, policy, risk tiers, approvals, evidence chain, execution grants) | CORE | Deterministic, non-LLM authorization decisions and hash-chained evidence. | A guarantee that actions outside WhitePact's declared enforcement boundary are blocked. |
| `responsibleai.isolation` | CORE | Runs a governed tool in a container with no network, read-only root, dropped capabilities and an unprivileged UID. Isolation is required by default. | Isolation for tools run outside the broker. Container tests on macOS are skipped, not passed. |
| `responsibleai.trust.TrustScoreEngine` | BETA | A weighted average of six values the **caller** supplies. | Independent verification of an agent's trustworthiness. |
| `responsibleai.compliance.ComplianceEngine` | BETA | Keyword matching of a use-case string to EU AI Act risk tiers; unknown use cases default to MINIMAL. | Legal classification or compliance advice. |
| `privacylabel.deepfake.DeepfakeDetector` | EXPERIMENTAL | One deterministic, uncalibrated Laplacian-variance signal. Needs `allow_experimental=True`. Results carry `validated=False`. No trained model ships; undecodable media raises. | Evidence of authenticity or manipulation. No error rate is known. |
| `responsibleai.hallucination.HallucinationDetector` | EXPERIMENTAL | TF-IDF agreement between candidate responses, hedging regexes, regexes for unattributed claims, and numeric/date disagreement with an optional source. | Fact verification. A confident wrong answer can score low risk. |
| `biasbuster` VADER sentiment divergence | EXPERIMENTAL | Optional; needs `nltk` and a pre-provisioned lexicon. It never downloads at scoring time and reports 0.0 when unavailable. | A bias finding on its own. |

Anything that consumes an EXPERIMENTAL or caller-supplied score (for example the trust
score's `authenticity` input) inherits its limits. Experimental results must not influence an
independently enforced authorization decision as if they were validated evidence.
