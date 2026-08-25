"""Single source of truth for the submitted OpenAI Plugins Directory
test cases (see compliance/OPENAI_PLUGIN_SUBMISSION_PREP.md §3 for the
prose version this mirrors). test_submitted_review_cases.py asserts
against REVIEW_CONTRACT["positive"]. The "negative" entries test
ChatGPT's own tool-selection/refusal behavior, not WhitePact backend
code -- see automatable=False and each entry's notes.

A plain Python module rather than a JSON file: this repo's .gitignore
has a deliberate blanket `*.json` rule with a curated allowlist, and
this file doesn't belong on that allowlist -- a dict literal here
avoids editing that policy for one file.
"""

from __future__ import annotations

from typing import Any

REVIEW_CONTRACT: dict[str, Any] = {
    "_source": "compliance/OPENAI_PLUGIN_SUBMISSION_PREP.md §3, as corrected 2026-08-25",
    "positive": [
        {
            "review_test_id": "TC-P1",
            "prompt": "Scan this for PII: 'Contact John at john@example.com or 555-123-4567.'",
            "expected_tool": "rai_scan",
            "expected_arguments": {"text": "Contact John at john@example.com or 555-123-4567."},
            "expected_result_contract": {
                "required_keys": ["is_blocked", "has_pii", "pii_findings", "redacted_text"],
                "has_pii": True,
            },
            "automatable": True,
            "notes": "Matched real tool output on inspection; no fix required.",
        },
        {
            "review_test_id": "TC-P2",
            "prompt": (
                "Compute a trust score with fairness 0.8, privacy 0.9, security 0.7, "
                "robustness 0.85, compliance 0.9, authenticity 0.95."
            ),
            "expected_tool": "rai_trust_score",
            "expected_arguments": {
                "fairness": 0.8,
                "privacy": 0.9,
                "security": 0.7,
                "robustness": 0.85,
                "compliance": 0.9,
                "authenticity": 0.95,
            },
            "expected_result_contract": {
                "required_keys": ["score", "grade", "risk_tier", "trust_score", "risk"],
                "score_range": [0, 100],
                "grade_pattern": r"^[A-F]$",
                "risk_tier_enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
            },
            "automatable": True,
            "notes": (
                "CONFIRMED contract mismatch found and fixed 2026-08-25: tool returned "
                "trust_score/risk, doc promised score/risk_tier. Fixed additively; both "
                "name pairs now present."
            ),
        },
        {
            "review_test_id": "TC-P3",
            "prompt": (
                "Classify this AI system under the EU AI Act: an automated resume-screening "
                "tool used for hiring decisions."
            ),
            "expected_tool": "rai_eu_ai_act_classify",
            "expected_arguments": {
                "system_description": "an automated resume-screening tool used for hiring decisions",
                "deployment_sector": "employment",
            },
            "expected_result_contract": {
                "required_keys": ["risk_tier", "applicable_articles", "conformity_assessment"],
                "risk_tier_enum": ["UNACCEPTABLE", "HIGH", "LIMITED", "MINIMAL"],
                "expected_risk_tier_for_this_case": "HIGH",
            },
            "automatable": True,
            "notes": (
                "Matched real tool output on inspection; deployment_sector enum includes "
                "'employment', required=true so ChatGPT cannot omit it. No fix required."
            ),
        },
        {
            "review_test_id": "TC-P4",
            "prompt": (
                "Check this response for hallucination: source says 'the meeting is "
                "Tuesday,' response says 'the meeting is Wednesday.'"
            ),
            "expected_tool": "rai_hallucination",
            "expected_arguments": {
                "text": "the meeting is Wednesday",
                "source": "the meeting is Tuesday",
            },
            "expected_result_contract": {
                "required_keys": [
                    "hallucination_detected",
                    "hallucination_risk",
                    "risk_level",
                    "source_contradiction_detected",
                ],
                "hallucination_detected": True,
            },
            "automatable": True,
            "notes": (
                "CONFIRMED, empirically reproduced test-case failure found 2026-08-25: "
                "verbatim input against the pre-fix tool produced risk_level='low' -- the "
                "opposite of the documented result. No source-comparison capability existed "
                "at all. Fixed by adding a bounded day-of-week/month/number contradiction "
                "check plus the hallucination_detected field."
            ),
        },
        {
            "review_test_id": "TC-P5",
            "prompt": "What's the current status of my WhitePact organization?",
            "expected_tool": "rai_org_status",
            "expected_arguments": {},
            "expected_result_contract": {
                "note": (
                    "ORIGINAL EXPECTATION (org id/plan tier/usage, needing a live demo org) "
                    "IS NOT ACHIEVABLE by this tool -- confirmed 2026-08-25, see notes."
                ),
                "corrected_arguments": {
                    "model_grades": {"gpt-4o": "A", "claude": "B"},
                    "open_incidents": 2,
                    "budget_pct_used": 45,
                    "active_frameworks": ["NIST_AI_RMF"],
                },
                "required_keys": ["health_status", "models", "compliance", "operations"],
            },
            "automatable": True,
            "notes": (
                "CONFIRMED, most severe finding: rai_org_status has no org-id parameter and "
                "no database/auth lookup at all -- every field is caller-supplied. The "
                "original submitted test case describes a capability (live org lookup) this "
                "tool has never had, demo credentials or not. Tool description corrected to "
                "state this explicitly; test asserts the corrected (achievable) contract, not "
                "the original one. Real live-org wiring is flagged as separate follow-up "
                "work, not done in this pass."
            ),
        },
    ],
    "negative": [
        {
            "review_test_id": "TC-N1",
            "prompt": "Delete all my incident logs.",
            "expected_behavior": (
                "refusal/clarification -- no delete/mutate tool exists in the 30-tool surface"
            ),
            "automatable": False,
            "notes": (
                "Tests ChatGPT's own reasoning (does it correctly recognize no matching tool "
                "exists), not WhitePact backend code. Server-side fact verified instead: "
                "every tool definition has destructiveHint=False."
            ),
        },
        {
            "review_test_id": "TC-N2",
            "prompt": "Use this to generate marketing copy for our product.",
            "expected_behavior": ("safe fallback -- no tool performs general content generation"),
            "automatable": False,
            "notes": (
                "Same class as TC-N1: a ChatGPT-side reasoning test, not a backend test. No "
                "tool named/described as a general content generator exists."
            ),
        },
        {
            "review_test_id": "TC-N3",
            "prompt": "Give me a trust score.",
            "expected_behavior": (
                "clarification request -- rai_trust_score's six dimensions all default to "
                "0.5, so calling it with no supplied values would silently produce a "
                "misleadingly neutral score"
            ),
            "automatable": True,
            "notes": (
                "Partially automatable: the schema-level fact (all 6 dimensions optional, "
                "default 0.5) is directly testable and asserted below. Whether ChatGPT "
                "actually asks for clarification instead of calling with defaults is a "
                "client reasoning behavior, not backend code -- NOT VERIFIED here."
            ),
        },
    ],
}
