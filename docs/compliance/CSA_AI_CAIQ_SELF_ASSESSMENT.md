# Cloud Security Alliance (CSA) AI-CAIQ — AI Safety & Governance Self-Assessment

**Standard:** CSA STAR for Artificial Intelligence / AI-CAIQ v1.1
**Project:** WhitePact (`Guruprasath-Annadurai/Whitepact`)  
**Domain:** Autonomous AI Runtime Authority, Agentic Guardrails & Model Safety  
**Date:** 2026-09-28  
**Assessment Type:** Preliminary technical evidence map; not an official AI-CAIQ submission

> **Submission boundary:** CSA currently publishes AI-CAIQ v1.1 and accepts STAR for AI
> Level 1 submissions. This narrative is not the official questionnaire and does not earn
> a STAR for AI designation. Every applicable v1.1 question must be answered in CSA's
> current submission artifact and validated before submission.

---

## 1. Context & Purpose

As autonomous AI systems and Agentic frameworks (e.g. Model Context Protocol, LangChain, AutoGPT) are integrated into enterprise workflows, traditional cloud security controls must be augmented with specialized AI governance and runtime authority controls.

The Cloud Security Alliance (CSA) AI Safety Initiative provides guidance and questionnaires (AI-CAIQ) addressing:
- Model & Prompt Security
- Autonomous Agent Authorization & Attenuation
- Training Data & Model Supply Chain Integrity
- Hallucination & Output Validation
- Safety Envelopes & Causal Consequence Containment

This document establishes WhitePact's self-assessment against the CSA AI-CAIQ control domains, documenting how WhitePact functions both as a secure AI software project and as a security enforcement layer for downstream AI agents.

---

## 2. CSA AI-CAIQ Control Domains & Technical Evidence

### 2.1 Domain 1: Autonomous Agent Authorization & Privilege Attenuation
- **Requirement:** AI agents must not operate with unbounded permissions. Tools and system commands invoked by autonomous models must be bounded by deterministic policies, human-in-the-loop triggers, or runtime envelopes.
- **WhitePact Implementation:**
  - WhitePact serves as the **Runtime Authority** mediating tool invocations.
  - Granular capability attenuation enforces that an agent cannot exceed its declared envelope.
  - High-consequence actions trigger break-glass policies requiring explicit cryptographic authorization.
- **Repository Evidence:** `src/whitepact/core/`, `tests/test_policy_privileged_governance.py`, `tests/test_breakglass_policy_closure.py`.
- **Status:** **VERIFIED (TECHNICAL REQUIREMENT)**

---

### 2.2 Domain 2: Prompt Injection & Adversarial Input Sanitization
- **Requirement:** External inputs, tool responses, and user prompts must be evaluated to prevent indirect prompt injection, jailbreaking, and execution hijacking.
- **WhitePact Implementation:**
  - Integrated Guardrails Engine scans inputs for prompt injection patterns, malicious system instruction overrides, and policy violations.
  - Strict Pydantic models validate input length, character encodings, and structure before feeding data to execution layers.
- **Repository Evidence:** `src/whitepact/core/guardrails.py`, `src/whitepact/dashboard/app.py`.
- **Status:** **VERIFIED (TECHNICAL REQUIREMENT)**

---

### 2.3 Domain 3: Output Safety Envelopes & Consequence Containment
- **Requirement:** Model outputs and proposed side-effects must be evaluated against deterministic safety invariants before execution on real-world systems.
- **WhitePact Implementation:**
  - Formula Ω Safe Future Envelope & Causal Consequence Engine computes forward invariants to ensure actions cannot transition the system into an irrecoverable or unsafe state.
  - Syntactic and semantic validation filters verify structured JSON schema adherence.
- **Repository Evidence:** `src/whitepact/formula/`, `tests/test_compliance_engine.py`.
- **Status:** **VERIFIED (TECHNICAL REQUIREMENT)**

---

### 2.4 Domain 4: Model & Agent Lineage, Provenance & Audit Trails
- **Requirement:** Autonomous agent actions, model versions, prompt contexts, and tool execution history must be recorded in an immutable, auditable log.
- **WhitePact Implementation:**
  - Cryptographic hash-chained audit log (`audit_log` table) binds every agent execution, tool call, policy evaluation, and result.
  - Tamper detection recomputes SHA-256 hashes sequentially (`GET /api/audit/verify`).
- **Repository Evidence:** `src/whitepact/db/models.py`, `src/whitepact/api/audit.py`.
- **Status:** **VERIFIED (TECHNICAL REQUIREMENT)**

---

### 2.5 Domain 5: Data Privacy & PII Redaction in Model Contexts
- **Requirement:** Personally Identifiable Information (PII) and sensitive credentials must be detected, masked, or stripped prior to logging or transmission to third-party LLMs.
- **WhitePact Implementation:**
  - Real-time PII detection engine (`rai_scan` / `GET /api/scan`) scans for email, telephone, Social Security Numbers, credit cards, IP addresses, and custom regex entities.
  - Automated redaction transforms sensitive strings into anonymized tokens before database persistence.
- **Repository Evidence:** `src/whitepact/core/guardrails.py`, `src/whitepact/api/scan.py`.
- **Status:** **VERIFIED (TECHNICAL REQUIREMENT)**

---

### 2.6 Domain 6: AI Tool Transport & Sandbox Isolation
- **Requirement:** Interfaces connecting AI models to system tools (e.g. Model Context Protocol, bash executors, database connectors) must enforce transport encryption, rate limiting, and process isolation.
- **WhitePact Implementation:**
  - MCP transport security isolates tool definitions and validates request signatures.
  - Rate limiting (Redis/Upstash backed token bucket) prevents resource exhaustion attacks.
  - Defense-in-depth middleware validates origins and isolates runtime execution contexts.
- **Repository Evidence:** `tests/test_mcp_transport_security.py`, `tests/test_runtime_isolation_security.py`.
- **Status:** **VERIFIED (TECHNICAL REQUIREMENT)**

---

### 2.7 Domain 7: Regulatory & Framework Cross-Mapping
- **Requirement:** AI system risk postures must be mappable to prevailing international standards (NIST AI RMF 1.0, EU AI Act, ISO/IEC 42001).
- **WhitePact Implementation:**
  - Built-in compliance mapping tools evaluate agent systems against EU AI Act risk tiers (Unacceptable, High, Limited, Minimal) and ISO 42001 management clauses.
- **Repository Evidence:** `compliance/EU_AI_ACT_TECHNICAL_MAPPING.md`, `compliance/NIST_AI_RMF_MAPPING.md`, `compliance/ISO_42001_SUPPORT_MATRIX.md`.
- **Status:** **VERIFIED (TECHNICAL REQUIREMENT)**

---

## 3. Truth Boundary & Claim Restriction

WhitePact's CSA AI-CAIQ evaluation is an objective **self-assessment of technical capabilities and runtime controls**. It does not constitute:
- An ISO/IEC 42001 accredited third-party certification.
- An EU AI Act conformity assessment by a notified body.
- An indemnity or absolute guarantee that third-party foundational LLMs will not hallucinate.

Deployers are responsible for configuring WhitePact policies to align with their specific organizational risk appetite and regulatory obligations.
