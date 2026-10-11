# Experimental and stub modules

WhitePact's governance core (`responsibleai.governance`: gateway, policy,
risk tiering, evidence chain, approvals) is the supported, tested part of the
project. The modules below ship in the same package but are **not**
production-grade. Do not base real decisions on their output.

| Module | Status | What it actually does |
|---|---|---|
| `privacylabel.deepfake.DeepfakeDetector` | **Stub** | No trained weights are shipped. With torch installed it runs XceptionNet/EfficientNet architectures with untrained, seeded weights; without torch it uses a Laplacian-variance heuristic on the image pixels. Video analysis without OpenCV raises `NotImplementedError`. Results carry `metadata["experimental"] = True`. Scores are deterministic but not meaningful. |
| `responsibleai.hallucination.HallucinationDetector` | **Experimental heuristic** | Combines TF-IDF agreement between several candidate responses with regex signals for hedging language and unattributed numbers/dates. It does not check claims against any source of truth, so it is not fact verification. |

Anything that consumes these scores (for example the trust score's
`authenticity` dimension when fed from the deepfake detector) inherits the
same limitation.
