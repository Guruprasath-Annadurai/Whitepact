# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from biasbuster.providers.base import BaseProvider, CompletionRequest, CompletionResponse

TEST_GOVERNANCE_PURPOSE = "automated-test"


@pytest.fixture
def seed_runtime_authority():
    """Seed explicit test-only root, consent, and delegation records."""
    async def seed(
        engine,
        *,
        organization_id: str,
        principal_id: str,
        action_types: tuple[str, ...],
        targets: tuple[str, ...],
        purpose: str = TEST_GOVERNANCE_PURPOSE,
    ):
        from responsibleai.db.consent_proof_repository import ConsentProofRepository
        from responsibleai.db.delegation_repository import DelegationRepository
        from responsibleai.db.root_authority_repository import RootAuthorityRepository
        from responsibleai.governance.consent_proof import ConsentMethod, build_consent_proof
        from responsibleai.governance.root_authority import RootType, build_root_authority_record

        owner = f"test-owner:{organization_id}"
        expires = datetime.now(UTC) + timedelta(hours=1)
        root = build_root_authority_record(
            owner,
            RootType.HUMAN,
            "whitepact-test-suite",
            "explicit-test-fixture",
            organization_id=organization_id,
            evidence_refs=("test-root-evidence",),
            expires_at=expires,
        )
        await RootAuthorityRepository(engine).create(root)
        consent = build_consent_proof(
            owner,
            root.root_id,
            principal_id,
            "explicit test execution scope",
            purpose,
            ConsentMethod.EXPLICIT_UI_ACTION,
            allowed_action_types=action_types,
            allowed_targets=targets,
            evidence_refs=("test-consent-evidence",),
            expires_at=expires,
        )
        await ConsentProofRepository(engine).create(consent, organization_id=organization_id)
        await DelegationRepository(engine).grant(
            organization_id,
            principal_id,
            granted_action_types=frozenset(action_types),
            constraints={"allowed_targets": list(targets)},
            purpose=purpose,
            granted_by=owner,
            expires_at=expires,
        )
        return root, consent

    return seed


class MockProvider(BaseProvider):
    """
    Deterministic provider for unit tests.

    Pass a dict mapping prompt substrings to responses.
    Unmatched prompts return ``default_response``.
    """

    def __init__(
        self,
        responses: dict[str, str] | None = None,
        default_response: str = "This is a generic test response about the person.",
    ) -> None:
        self._responses = responses or {}
        self._default = default_response
        self.call_count = 0

    @property
    def name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-1.0"

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.call_count += 1
        for key, response in self._responses.items():
            if key in request.prompt:
                return CompletionResponse(
                    text=response,
                    model=self.model_name,
                    provider=self.name,
                    input_tokens=len(request.prompt.split()),
                    output_tokens=len(response.split()),
                )
        return CompletionResponse(
            text=self._default,
            model=self.model_name,
            provider=self.name,
        )


class BiasedMockProvider(MockProvider):
    """
    Provider that returns noticeably different responses per gender,
    used to test that the probe correctly flags bias.
    """

    _MASCULINE_RESPONSE = (
        "James is a decisive and assertive leader with strong technical vision. "
        "He commands respect from his team and drives results with confidence. "
        "His strategic thinking and bold approach make him ideal for senior roles. "
        "James demonstrates exceptional problem-solving and mentors junior engineers."
    )
    _FEMININE_RESPONSE = (
        "Mary is a collaborative and supportive team member who helps others. "
        "She is kind, empathetic, and good at communicating. "
        "She works well in a team environment and keeps morale high. "
        "Mary is helpful and approachable, making her a pleasant colleague."
    )
    _NEUTRAL_RESPONSE = (
        "Alex is a software engineer with experience in distributed systems. "
        "They have contributed to multiple projects and work well with their team. "
        "Alex has demonstrated solid technical skills across several domains."
    )

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.call_count += 1
        prompt = request.prompt

        if "James" in prompt:
            text = self._MASCULINE_RESPONSE
        elif "Mary" in prompt:
            text = self._FEMININE_RESPONSE
        elif "Alex" in prompt:
            text = self._NEUTRAL_RESPONSE
        else:
            text = self._default

        return CompletionResponse(text=text, model=self.model_name, provider=self.name)


class UnbiasedMockProvider(MockProvider):
    """
    Provider that returns structurally identical responses regardless of gender.
    Used to confirm that the probe correctly passes unbiased models.
    """

    _TEMPLATE = (
        "{name} is an experienced software engineer with a strong track record "
        "of delivering high-quality systems. They have demonstrated expertise in "
        "distributed architectures and led cross-functional teams effectively. "
        "Their technical skills and collaborative approach make them well-suited "
        "for senior engineering roles."
    )

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.call_count += 1

        for first_name in ["James", "Mary", "Alex"]:
            if first_name in request.prompt:
                text = self._TEMPLATE.format(name=first_name)
                return CompletionResponse(text=text, model=self.model_name, provider=self.name)

        return CompletionResponse(
            text=self._TEMPLATE.format(name="the engineer"),
            model=self.model_name,
            provider=self.name,
        )


@pytest.fixture
def mock_provider() -> MockProvider:
    return MockProvider()


@pytest.fixture
def biased_provider() -> BiasedMockProvider:
    return BiasedMockProvider()


@pytest.fixture
def unbiased_provider() -> UnbiasedMockProvider:
    return UnbiasedMockProvider()
