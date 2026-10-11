# WhitePact Feature Maturity & Capability Register

## 1. Classification Framework

Statuses:
- **CORE**: Primary runtime authorization kernel, tenant isolation, and cryptographic audit chain. Production-candidate level; independent verification / third-party audit pending.
- **BETA**: Implemented and tested subsystems with known domain boundaries (e.g., caller-supplied heuristics, rule engines).
- **EXPERIMENTAL**: Heuristics, statistical indicators, or prototype detectors. Requires explicit opt-in flags. Results carry `validated=False` and must never serve as authoritative authorization evidence.
- **DEPRECATED**: Legacy aliases or backward-compatibility shims slated for future removal.
- **UNSUPPORTED**: Stubs or capabilities without verified enforcement.

> [!IMPORTANT]
> **No module is rated STABLE or Enterprise-Certified.**
> Staging status requires an independent third-party audit of the exact release tree. WhitePact operates under **GLOBAL PRODUCTION NO-GO** until qualified through verified staging.

---

## 2. Comprehensive Module Register

| Module / Subsystem | Status | Source Implementation | Primary Test Evidence | What It Actually Does | Must Not Be Used As |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Governance Engine** (`responsibleai.governance`) | **CORE** | `src/responsibleai/governance/` | `tests/test_governance.py`, `tests/test_audit_trail.py` | Deterministic, non-LLM policy evaluation, risk tiering, human-in-the-loop approvals, Ed25519 hash-chained audit witness log. | A guarantee that unmonitored actions executed outside WhitePact's declared broker boundary are blocked. |
| **Execution Isolation & In-Flight Containment** (`responsibleai.isolation`) | **CORE** | `src/responsibleai/isolation/` | `tests/test_isolation_*.py`, `tests/test_in_flight_revocation.py` | Runs governed tools in unprivileged containers or subprocesses; terminates in-flight execution via SIGKILL upon revocation epoch bump. | Tool execution outside broker. Container tests on macOS are skipped (requires Linux cgroups/namespaces). |
| **Sovereign Authority Kernel** (`responsibleai.sovereign`) | **CORE** | `src/responsibleai/sovereign/` | `tests/sovereign/test_*.py` | Multi-tenant authority graph, capability capsules, zero-effect simulation, drift detection, and contract gauntlet. | Cross-cloud identity federator without verified enterprise IdP provisioning. |
| **Database & Multi-Tenant Isolation** (`responsibleai.db`) | **CORE** | `src/responsibleai/db/` | `tests/test_postgres_*.py`, `tests/test_database_migrations.py` | Multi-tenant relational persistence (PostgreSQL/SQLite), revocation epochs, nonces, idempotent migrations. | Shared database accessible to untrusted execution workers. |
| **RBAC, Privileged Guards & Four-Eyes** (`responsibleai.rbac`, `responsibleai.auth`) | **CORE** | `src/responsibleai/rbac/`, `src/responsibleai/auth/` | `tests/test_privileged_surface_guard.py` | Tiered role-based access, MFA step-up validation, and mandatory four-eyes quorum for enterprise staging. | Single-admin bypass in production/staging environments. |
| **MCP Authority Gateway** (`responsibleai.mcp`) | **CORE** | `src/responsibleai/mcp/` | `tests/test_mcp_authority_tools.py` | Exposes read-only authority tools (Option B) to agents while keeping execution strictly separate from workers. | A permission granting arbitrary worker tool execution without gateway brokering. |
| **LangGraph / Workflow Integration** (`responsibleai.integrations`) | **BETA** | `src/responsibleai/integrations/langgraph.py` | `tests/test_langgraph_gate.py` | State-graph trust gate intercepting agent action steps before execution; enforces allow/deny/human-approval. | Autonomous agent safety validator without governed tool brokers. |
| **Trust Score Engine** (`responsibleai.trust`) | **BETA** | `src/responsibleai/trust/` | `tests/test_scoring.py` | Weighted arithmetic average of six dimensions supplied directly by the **caller**. | Independent verification of an agent's real-world trustworthiness. |
| **Compliance Engine** (`responsibleai.compliance`) | **BETA** | `src/responsibleai/compliance/` | `tests/test_compliance.py` | Keyword matching of use-case descriptions against EU AI Act risk categories; unknown use cases default to MINIMAL. | Legal compliance certification, regulatory advice, or comprehensive risk assessment. |
| **Deepfake Detector** (`privacylabel.deepfake`) | **EXPERIMENTAL** | `src/privacylabel/deepfake/detector.py` | `tests/test_deepfake_detector.py` | Uncalibrated, deterministic Laplacian variance heuristic on decoded image frames. Requires `allow_experimental=True`. Returns `validated=False`. | Proof of media authenticity or absence of manipulation. Error rates are uncalibrated. |
| **Hallucination Detector** (`responsibleai.hallucination`) | **EXPERIMENTAL** | `src/responsibleai/hallucination/` | `tests/test_hallucination.py` | TF-IDF token consistency across candidates, regex hedging/attribution checks, date/numeric comparison. | Independent ground-truth factual verification. Confident false statements score low risk. |
| **Sentiment Divergence** (`biasbuster.core`) | **EXPERIMENTAL** | `src/biasbuster/core/` | `tests/test_gender_bias.py` | VADER sentiment lexicon divergence. Requires pre-installed NLTK lexicon; returns `0.0` offline without downloading. | Definitive finding of societal or model bias on its own. |
| **Legacy CLI Alias** (`biasbuster`, `responsibleai`) | **DEPRECATED** | `src/whitepact/cli.py` | `tests/test_whitepact_cli_entrypoint.py` | Forwarding wrappers mapping legacy commands to canonical `whitepact` CLI. | Long-term stable CLI interface (use `whitepact` exclusively). |

---

## 3. Detailed Heuristic Limitations & Protocols

### 3.1 Deepfake Detection (`DeepfakeDetector`)
- **Underlying Mechanism**: Calculates Laplacian variance over grayscale pixel matrices to measure edge sharpness.
- **Opt-In Guard**: Raises `RuntimeError` unless initialized with `allow_experimental=True`.
- **Output Contract**: Emits `{"validated": False, "score": float, "heuristic": "laplacian_variance"}`.
- **Prohibited Uses**: Must never be used in legal proceedings, identity verification, KYC, or safety-critical content moderation.

### 3.2 Hallucination Detection (`HallucinationDetector`)
- **Underlying Mechanism**: Evaluates consistency between multiple LLM outputs using TF-IDF n-gram overlap, detects linguistic hedging expressions (`"it is possible"`, `"as far as I know"`), and flags unanchored assertions.
- **Failure Modes**: Syntactically confident, internally consistent hallucinations score as low risk.
- **Prohibited Uses**: Must never be represented to users as factual verification or truth checking.

### 3.3 Trust Score Engine (`TrustScoreEngine`)
- **Underlying Mechanism**: Computes `S = Σ (w_i * d_i)` where dimensions `d_i` (safety, reliability, privacy, transparency, alignment, authenticity) are numbers passed directly in the request payload by the client application.
- **Prohibited Uses**: Must never be claimed as WhitePact evaluating an agent's objective trustworthiness.

### 3.4 Bias & Sentiment Probes (`biasbuster`)
- **Offline Integrity**: VADER sentiment evaluation uses only pre-provisioned local data. At runtime, zero network requests or NLTK corpus downloads are permitted. Missing lexicons default gracefully to `0.0`.
- **Prohibited Uses**: Does not replace formal fair-lending, demographic parity, or protected-class statistical testing.

---

## 4. Operational Invariant

> **The agent may think freely. It may plan freely. But it cannot act outside independently enforced authority.**

Any score produced by an **EXPERIMENTAL** or **BETA** module that feeds into a policy decision inherits that module's experimental status and cannot be treated as verified cryptographic evidence.
