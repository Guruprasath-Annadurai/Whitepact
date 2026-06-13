from __future__ import annotations

import pytest

from biasbuster.probes.occupational_stereotype import (
    DEFAULT_TEMPLATES,
    JOBS,
    OccupationalStereotypeProbe,
    pronoun_injection_score,
)
from biasbuster.providers.base import BaseProvider, CompletionRequest, CompletionResponse


class GenderedProvider(BaseProvider):
    """Injects strong gendered pronouns — should score high."""

    _RESPONSES = {
        "nurse": "The nurse entered the room. She checked the patient's chart carefully. Her compassionate manner put the patient at ease. She administered the medication as prescribed.",
        "software engineer": "The software engineer sat down at his desk. He opened his laptop and began reviewing his code. His technical skills were evident as he debugged the issue efficiently.",
        "CEO": "The CEO walked into the boardroom. He commanded the room with confidence. His strategic vision was clear as he outlined his plan for the company's future growth.",
    }
    _DEFAULT = "They did their job professionally and competently each day."

    @property
    def name(self) -> str:
        return "mock-gendered"

    @property
    def model_name(self) -> str:
        return "mock-1.0"

    def __init__(self) -> None:
        self.call_count = 0

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.call_count += 1
        for job, response in self._RESPONSES.items():
            if job in request.prompt.lower():
                return CompletionResponse(
                    text=response, model=self.model_name, provider=self.name
                )
        return CompletionResponse(text=self._DEFAULT, model=self.model_name, provider=self.name)


class NeutralProvider(BaseProvider):
    """Uses only neutral pronouns — should score near zero."""

    _TEMPLATE = (
        "The {job} arrived at work and began their daily responsibilities. "
        "They reviewed their tasks and coordinated with their colleagues. "
        "Their professionalism and dedication were evident throughout the day. "
        "They completed their work to a high standard."
    )

    @property
    def name(self) -> str:
        return "mock-neutral"

    @property
    def model_name(self) -> str:
        return "mock-1.0"

    def __init__(self) -> None:
        self.call_count = 0

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.call_count += 1
        for job, _ in JOBS:
            if job in request.prompt.lower():
                return CompletionResponse(
                    text=self._TEMPLATE.format(job=job),
                    model=self.model_name,
                    provider=self.name,
                )
        return CompletionResponse(
            text=self._TEMPLATE.format(job="professional"),
            model=self.model_name,
            provider=self.name,
        )


class TestPronounInjectionScore:
    def test_all_gendered_returns_one(self) -> None:
        text = "He walked in. He sat down. His briefcase was on the desk. He opened it."
        score = pronoun_injection_score(text)
        assert score == pytest.approx(1.0)

    def test_all_neutral_returns_zero(self) -> None:
        text = "They walked in. They sat down. Their briefcase was on the desk."
        score = pronoun_injection_score(text)
        assert score == pytest.approx(0.0)

    def test_no_pronouns_returns_zero(self) -> None:
        text = "The engineer completed the task and submitted the report."
        score = pronoun_injection_score(text)
        assert score == 0.0

    def test_mixed_returns_ratio(self) -> None:
        text = "She finished the report. They submitted it. He reviewed it."
        score = pronoun_injection_score(text)
        assert 0.0 < score < 1.0

    def test_score_bounded(self) -> None:
        texts = [
            "He his him himself",
            "She her hers herself",
            "They them their themselves",
            "",
        ]
        for text in texts:
            score = pronoun_injection_score(text)
            assert 0.0 <= score <= 1.0

    def test_case_insensitive(self) -> None:
        lower = pronoun_injection_score("he walked in")
        upper = pronoun_injection_score("HE walked in")
        assert lower == upper


class TestOccupationalStereotypeProbeWithGenderedProvider:
    @pytest.mark.asyncio
    async def test_flags_gendered_provider(self) -> None:
        probe = OccupationalStereotypeProbe(
            jobs=JOBS[:3], templates=DEFAULT_TEMPLATES[:1], threshold=0.25
        )
        result = await probe.run(GenderedProvider())
        assert result.overall_score > 0.25, (
            f"Expected score > 0.25 for gendered provider, got {result.overall_score:.4f}"
        )

    @pytest.mark.asyncio
    async def test_job_scores_in_metadata(self) -> None:
        probe = OccupationalStereotypeProbe(jobs=JOBS[:3], templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(GenderedProvider())
        assert "job_scores" in result.metadata
        assert len(result.metadata["job_scores"]) == 3

    @pytest.mark.asyncio
    async def test_worst_job_populated(self) -> None:
        probe = OccupationalStereotypeProbe(jobs=JOBS[:3], templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(GenderedProvider())
        assert "worst_job" in result.metadata
        assert result.metadata["worst_job"] is not None

    @pytest.mark.asyncio
    async def test_template_metadata_has_job_info(self) -> None:
        probe = OccupationalStereotypeProbe(jobs=JOBS[:2], templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(GenderedProvider())
        for tr in result.template_results:
            assert "job_title" in tr.metadata
            assert "societal_stereotype" in tr.metadata
            assert "gendered_pronoun_count" in tr.metadata
            assert "neutral_pronoun_count" in tr.metadata

    @pytest.mark.asyncio
    async def test_each_template_has_single_response(self) -> None:
        probe = OccupationalStereotypeProbe(jobs=JOBS[:2], templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(GenderedProvider())
        for tr in result.template_results:
            assert len(tr.variant_responses) == 1
            assert tr.variant_responses[0].variant_name == "single"

    @pytest.mark.asyncio
    async def test_provider_call_count(self) -> None:
        n_jobs = 3
        n_templates = 2
        provider = GenderedProvider()
        probe = OccupationalStereotypeProbe(
            jobs=JOBS[:n_jobs], templates=DEFAULT_TEMPLATES[:n_templates]
        )
        await probe.run(provider)
        assert provider.call_count == n_jobs * n_templates


class TestOccupationalStereotypeProbeWithNeutralProvider:
    @pytest.mark.asyncio
    async def test_passes_neutral_provider(self) -> None:
        probe = OccupationalStereotypeProbe(
            jobs=JOBS[:5], templates=DEFAULT_TEMPLATES[:1], threshold=0.25
        )
        result = await probe.run(NeutralProvider())
        assert result.passed, (
            f"Expected neutral provider to pass, got score {result.overall_score:.4f}"
        )

    @pytest.mark.asyncio
    async def test_low_score_for_neutral(self) -> None:
        probe = OccupationalStereotypeProbe(jobs=JOBS[:5], templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(NeutralProvider())
        assert result.overall_score < 0.10


class TestOccupationalStereotypeResultShape:
    @pytest.mark.asyncio
    async def test_probe_name(self) -> None:
        probe = OccupationalStereotypeProbe(jobs=JOBS[:1], templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(NeutralProvider())
        assert result.probe_name == "occupational-stereotype"

    @pytest.mark.asyncio
    async def test_to_dict_serialisable(self) -> None:
        import json

        probe = OccupationalStereotypeProbe(jobs=JOBS[:1], templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(NeutralProvider())
        assert isinstance(json.dumps(result.to_dict()), str)

    @pytest.mark.asyncio
    async def test_score_bounded(self) -> None:
        probe = OccupationalStereotypeProbe(jobs=JOBS[:3], templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(GenderedProvider())
        assert 0.0 <= result.overall_score <= 1.0
