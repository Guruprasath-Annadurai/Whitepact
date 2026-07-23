"""Tests for TOTP MFA business logic (responsibleai.auth.mfa)."""

from __future__ import annotations

import pyotp

from responsibleai.auth import mfa


class TestSecretAndProvisioning:
    def test_generate_secret_is_valid_base32(self) -> None:
        secret = mfa.generate_secret()
        assert len(secret) >= 16
        # Must round-trip through pyotp without raising.
        pyotp.TOTP(secret).now()

    def test_generate_secret_is_random(self) -> None:
        assert mfa.generate_secret() != mfa.generate_secret()

    def test_provisioning_uri_contains_account_and_issuer(self) -> None:
        secret = mfa.generate_secret()
        uri = mfa.provisioning_uri(secret, account_name="ci-key", issuer="ResponsibleAI")
        assert uri.startswith("otpauth://totp/")
        assert "ResponsibleAI" in uri
        assert "secret=" + secret in uri


class TestVerifyCode:
    def test_valid_code_verifies(self) -> None:
        secret = mfa.generate_secret()
        code = pyotp.TOTP(secret).now()
        assert mfa.verify_code(secret, code) is True

    def test_wrong_code_rejected(self) -> None:
        secret = mfa.generate_secret()
        real_code = pyotp.TOTP(secret).now()
        wrong_code = "000000" if real_code != "000000" else "111111"
        assert mfa.verify_code(secret, wrong_code) is False

    def test_empty_code_rejected(self) -> None:
        secret = mfa.generate_secret()
        assert mfa.verify_code(secret, "") is False

    def test_non_numeric_code_rejected(self) -> None:
        secret = mfa.generate_secret()
        assert mfa.verify_code(secret, "abcdef") is False

    def test_code_from_different_secret_rejected(self) -> None:
        secret_a = mfa.generate_secret()
        secret_b = mfa.generate_secret()
        code_from_b = pyotp.TOTP(secret_b).now()
        # Extremely unlikely to collide, but guard against flakiness anyway.
        if pyotp.TOTP(secret_a).now() == code_from_b:
            return
        assert mfa.verify_code(secret_a, code_from_b) is False


class TestBackupCodes:
    def test_generates_ten_codes(self) -> None:
        codes = mfa.generate_backup_codes()
        assert len(codes) == 10

    def test_codes_are_unique(self) -> None:
        codes = mfa.generate_backup_codes()
        assert len(set(codes)) == len(codes)

    def test_hash_is_deterministic(self) -> None:
        assert mfa.hash_backup_code("ABCD1234EF") == mfa.hash_backup_code("ABCD1234EF")

    def test_hash_is_case_and_whitespace_insensitive(self) -> None:
        assert mfa.hash_backup_code(" abcd1234ef ") == mfa.hash_backup_code("ABCD1234EF")

    def test_hash_differs_for_different_codes(self) -> None:
        assert mfa.hash_backup_code("AAAAAAAAAA") != mfa.hash_backup_code("BBBBBBBBBB")

    def test_verify_and_consume_success_removes_code(self) -> None:
        codes = mfa.generate_backup_codes()
        hashed = [mfa.hash_backup_code(c) for c in codes]
        remaining = mfa.verify_and_consume_backup_code(hashed, codes[3])
        assert remaining is not None
        assert len(remaining) == len(hashed) - 1
        assert mfa.hash_backup_code(codes[3]) not in remaining

    def test_verify_and_consume_wrong_code_returns_none(self) -> None:
        codes = mfa.generate_backup_codes()
        hashed = [mfa.hash_backup_code(c) for c in codes]
        assert mfa.verify_and_consume_backup_code(hashed, "NOTACODE12") is None

    def test_verify_and_consume_empty_code_returns_none(self) -> None:
        hashed = [mfa.hash_backup_code(c) for c in mfa.generate_backup_codes()]
        assert mfa.verify_and_consume_backup_code(hashed, "") is None

    def test_consumed_code_cannot_be_reused(self) -> None:
        codes = mfa.generate_backup_codes()
        hashed = [mfa.hash_backup_code(c) for c in codes]
        remaining = mfa.verify_and_consume_backup_code(hashed, codes[0])
        assert remaining is not None
        assert mfa.verify_and_consume_backup_code(remaining, codes[0]) is None
