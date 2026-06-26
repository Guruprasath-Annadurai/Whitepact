from __future__ import annotations

from responsibleai.guardrails.engine import (
    GuardrailsEngine,
    GuardrailsPolicy,
)


class TestPIIDetection:
    def setup_method(self) -> None:
        self.engine = GuardrailsEngine()

    def test_clean_text_not_blocked(self) -> None:
        result = self.engine.scan("The patient responded well to treatment.")
        assert not result.is_blocked
        assert not result.has_pii

    def test_email_detected(self) -> None:
        result = self.engine.scan("Contact me at user@example.com for details.")
        assert result.has_pii
        cats = {f.category for f in result.pii_findings}
        assert "email" in cats

    def test_phone_detected(self) -> None:
        result = self.engine.scan("Call us at 555-867-5309 for an appointment.")
        assert result.has_pii
        cats = {f.category for f in result.pii_findings}
        assert "phone" in cats

    def test_ssn_detected(self) -> None:
        result = self.engine.scan("The patient's SSN is 123-45-6789.")
        assert result.has_pii
        cats = {f.category for f in result.pii_findings}
        assert "ssn" in cats

    def test_credit_card_detected(self) -> None:
        result = self.engine.scan("Card number: 4111 1111 1111 1111")
        assert result.has_pii
        cats = {f.category for f in result.pii_findings}
        assert "credit_card" in cats

    def test_ip_address_detected(self) -> None:
        result = self.engine.scan("Server IP is 192.168.1.100")
        assert result.has_pii
        cats = {f.category for f in result.pii_findings}
        assert "ip_address" in cats

    def test_multiple_pii_categories_detected(self) -> None:
        result = self.engine.scan(
            "Email: user@example.com, phone: 555-123-4567"
        )
        cats = {f.category for f in result.pii_findings}
        assert "email" in cats
        assert "phone" in cats

    def test_pii_blocked(self) -> None:
        result = self.engine.scan("user@example.com is the contact.")
        assert result.is_blocked

    def test_block_reasons_populated(self) -> None:
        result = self.engine.scan("Reach me at user@example.com")
        assert len(result.block_reasons) > 0
        assert any("PII" in r for r in result.block_reasons)


class TestPIIRedaction:
    def setup_method(self) -> None:
        self.engine = GuardrailsEngine(
            GuardrailsPolicy(block_pii=True, redact_pii=True)
        )

    def test_email_redacted(self) -> None:
        result = self.engine.scan("Contact user@example.com for help.")
        assert result.redacted_text is not None
        assert "user@example.com" not in result.redacted_text
        assert "[REDACTED]" in result.redacted_text

    def test_clean_text_has_no_redacted_text(self) -> None:
        result = self.engine.scan("This text contains no PII.")
        assert result.redacted_text is None

    def test_redaction_preserves_surrounding_text(self) -> None:
        result = self.engine.scan("Before user@example.com after.")
        assert result.redacted_text is not None
        assert "Before" in result.redacted_text
        assert "after" in result.redacted_text


class TestToxicityDetection:
    def setup_method(self) -> None:
        self.engine = GuardrailsEngine()

    def test_clean_text_no_toxicity(self) -> None:
        result = self.engine.scan("The weather is nice today.")
        assert not result.has_toxicity

    def test_violence_detected(self) -> None:
        result = self.engine.scan("This contains a bomb threat and mass shooting reference.")
        assert result.has_toxicity
        cats = {f.category for f in result.toxicity_findings}
        assert "violence" in cats

    def test_toxicity_blocked(self) -> None:
        result = self.engine.scan("This is a bomb threat.")
        assert result.is_blocked

    def test_toxicity_in_block_reasons(self) -> None:
        result = self.engine.scan("This contains a bomb threat.")
        assert any("Toxicity" in r or "toxicity" in r for r in result.block_reasons)


class TestCustomPatterns:
    def test_custom_pattern_matched(self) -> None:
        policy = GuardrailsPolicy(
            block_pii=False,
            block_toxicity=False,
            custom_blocked_patterns=[r"\bCONFIDENTIAL\b"],
        )
        engine = GuardrailsEngine(policy=policy)
        result = engine.scan("This document is CONFIDENTIAL.")
        assert result.is_blocked
        assert len(result.custom_pattern_matches) == 1

    def test_no_custom_pattern_not_blocked(self) -> None:
        policy = GuardrailsPolicy(
            block_pii=False,
            block_toxicity=False,
            custom_blocked_patterns=[r"\bSECRET\b"],
        )
        engine = GuardrailsEngine(policy=policy)
        result = engine.scan("This is a normal sentence.")
        assert not result.is_blocked


class TestGuardrailsPolicy:
    def test_pii_disabled(self) -> None:
        policy = GuardrailsPolicy(block_pii=False, block_toxicity=False)
        engine = GuardrailsEngine(policy=policy)
        result = engine.scan("Contact user@example.com")
        assert not result.is_blocked

    def test_toxicity_disabled(self) -> None:
        policy = GuardrailsPolicy(block_pii=False, block_toxicity=False)
        engine = GuardrailsEngine(policy=policy)
        result = engine.scan("This is a bomb threat.")
        assert not result.is_blocked


class TestGuardrailsResultToDict:
    def test_to_dict_structure(self) -> None:
        engine = GuardrailsEngine()
        result = engine.scan("Contact user@example.com")
        d = result.to_dict()
        required = {
            "is_blocked", "has_pii", "has_toxicity",
            "pii_findings", "toxicity_findings",
            "custom_pattern_matches", "block_reasons", "redacted_text",
        }
        assert required.issubset(d.keys())

    def test_to_dict_pii_finding_has_category(self) -> None:
        engine = GuardrailsEngine()
        result = engine.scan("Email: user@example.com")
        d = result.to_dict()
        assert d["pii_findings"][0]["category"] == "email"
