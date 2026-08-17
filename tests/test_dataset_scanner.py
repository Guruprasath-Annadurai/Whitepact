"""Tests for DatasetBiasScanner -- previously entirely untested in isolation."""

from __future__ import annotations

from responsibleai.eval.dataset_scanner import DatasetBiasScanner


class TestScanCsv:
    def test_scans_str_content_all_columns(self):
        scanner = DatasetBiasScanner()
        csv_content = "name,note\nAlice,she is a great engineer\nBob,he is a nurse\n"
        result = scanner.scan_csv(csv_content)
        assert result.total_rows == 2
        assert result.filename == "upload.csv"

    def test_scans_bytes_content(self):
        scanner = DatasetBiasScanner()
        csv_bytes = b"name,note\nAlice,she is great\n"
        result = scanner.scan_csv(csv_bytes)
        assert result.total_rows == 1

    def test_scans_only_specified_text_column(self):
        scanner = DatasetBiasScanner()
        csv_content = "id,note\n1,he is a doctor\n"
        result = scanner.scan_csv(csv_content, text_column="note")
        assert result.row_results[0].text == "he is a doctor"

    def test_falls_back_to_all_columns_when_text_column_absent(self):
        scanner = DatasetBiasScanner()
        csv_content = "id,note\n1,he is a doctor\n"
        result = scanner.scan_csv(csv_content, text_column="nonexistent_column")
        assert "1" in result.row_results[0].text
        assert "doctor" in result.row_results[0].text


class TestScanJsonl:
    def test_scans_str_content(self):
        scanner = DatasetBiasScanner()
        jsonl = '{"note": "she is a teacher"}\n{"note": "he is old"}\n'
        result = scanner.scan_jsonl(jsonl)
        assert result.total_rows == 2

    def test_scans_bytes_content(self):
        scanner = DatasetBiasScanner()
        jsonl = b'{"note": "hello"}\n'
        result = scanner.scan_jsonl(jsonl)
        assert result.total_rows == 1

    def test_skips_blank_lines(self):
        scanner = DatasetBiasScanner()
        jsonl = '{"note": "a"}\n\n   \n{"note": "b"}\n'
        result = scanner.scan_jsonl(jsonl)
        assert result.total_rows == 2

    def test_uses_specified_text_field_when_present(self):
        scanner = DatasetBiasScanner()
        jsonl = '{"other": "ignored", "note": "he is young"}\n'
        result = scanner.scan_jsonl(jsonl, text_field="note")
        assert result.row_results[0].text == "he is young"

    def test_falls_back_to_all_values_when_text_field_absent(self):
        scanner = DatasetBiasScanner()
        jsonl = '{"a": "x", "b": "y"}\n'
        result = scanner.scan_jsonl(jsonl, text_field="nonexistent")
        assert "x" in result.row_results[0].text
        assert "y" in result.row_results[0].text

    def test_non_dict_json_value_stringified(self):
        scanner = DatasetBiasScanner()
        jsonl = '"just a string"\n'
        result = scanner.scan_jsonl(jsonl)
        assert result.row_results[0].text == "just a string"

    def test_invalid_json_line_kept_as_raw_text(self):
        scanner = DatasetBiasScanner()
        jsonl = "not valid json at all\n"
        result = scanner.scan_jsonl(jsonl)
        assert result.row_results[0].text == "not valid json at all"


class TestScanTexts:
    def test_scans_list_of_strings(self):
        scanner = DatasetBiasScanner()
        result = scanner.scan_texts(["he is a boss", "clean text here"], filename="mydata")
        assert result.filename == "mydata"
        assert result.total_rows == 2


class TestRowFlagsAndScoring:
    def test_bias_category_detected_and_flagged(self):
        scanner = DatasetBiasScanner()
        result = scanner.scan_texts(["he is the engineer"])
        row = result.row_results[0]
        assert "gender" in row.bias_categories
        assert any(f.startswith("bias:") for f in row.flags)
        assert row.score > 0

    def test_pii_detected_flags_pii(self):
        scanner = DatasetBiasScanner()
        result = scanner.scan_texts(["contact me at test@example.com"])
        row = result.row_results[0]
        assert row.pii_detected is True
        assert "pii" in row.flags

    def test_toxicity_detected_flags_toxicity(self):
        scanner = DatasetBiasScanner()
        result = scanner.scan_texts(["that comment was made by a bigot"])
        row = result.row_results[0]
        assert row.toxicity_detected is True
        assert "toxicity" in row.flags

    def test_clean_text_has_no_flags_and_zero_score(self):
        scanner = DatasetBiasScanner()
        result = scanner.scan_texts(["the quick brown fox jumps"])
        row = result.row_results[0]
        assert row.flags == []
        assert row.score == 0.0

    def test_score_capped_at_one(self):
        scanner = DatasetBiasScanner()
        # gender + racial + age + religious + occupational + socioeconomic bias
        # categories plus PII, easily exceeding the 0.2-per-flag cap of 1.0.
        text = (
            "he she man woman white black old young christian muslim "
            "nurse doctor poor rich test@example.com 555-123-4567"
        )
        result = scanner.scan_texts([text])
        assert result.row_results[0].score == 1.0


class TestDetectBiasCategories:
    def test_multiple_categories_detected(self):
        cats = DatasetBiasScanner._detect_bias_categories("he is an old doctor")
        assert "gender" in cats
        assert "age" in cats
        assert "occupational" in cats

    def test_no_categories_for_neutral_text(self):
        cats = DatasetBiasScanner._detect_bias_categories("the sky is blue today")
        assert cats == []
