# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from privacylabel.deepfake import detector as detector_module
from privacylabel.deepfake.detector import (
    EXPERIMENTAL_NOTICE,
    VALIDATED_DETECTORS,
    DeepfakeDetector,
    DeepfakeResult,
    DetectorNotValidatedError,
    DetectorUnavailableError,
    UnreadableMediaError,
)
from privacylabel.deepfake.ensemble import EnsembleVoter, ModelScore, VotingStrategy


class TestEnsembleVoter:
    def test_mean_strategy_correct(self) -> None:
        voter = EnsembleVoter(strategy=VotingStrategy.MEAN, threshold=0.5)
        scores = [
            ModelScore("a", 0.3),
            ModelScore("b", 0.7),
        ]
        is_fake, score = voter.vote(scores)
        assert score == pytest.approx(0.5)

    def test_max_strategy_conservative(self) -> None:
        voter = EnsembleVoter(strategy=VotingStrategy.MAX, threshold=0.5)
        scores = [
            ModelScore("a", 0.3),
            ModelScore("b", 0.8),
        ]
        is_fake, score = voter.vote(scores)
        assert score == pytest.approx(0.8)
        assert is_fake

    def test_weighted_strategy(self) -> None:
        voter = EnsembleVoter(strategy=VotingStrategy.WEIGHTED, threshold=0.5)
        scores = [
            ModelScore("a", 0.0, weight=3.0),
            ModelScore("b", 1.0, weight=1.0),
        ]
        is_fake, score = voter.vote(scores)
        # (0.0*3 + 1.0*1) / 4 = 0.25
        assert score == pytest.approx(0.25)
        assert not is_fake

    def test_majority_strategy(self) -> None:
        voter = EnsembleVoter(strategy=VotingStrategy.MAJORITY, threshold=0.5)
        scores = [
            ModelScore("a", 0.9),  # fake vote
            ModelScore("b", 0.9),  # fake vote
            ModelScore("c", 0.1),  # real vote
        ]
        is_fake, score = voter.vote(scores)
        # 2/3 vote fake → 0.667 > 0.5
        assert is_fake

    def test_empty_scores_returns_false(self) -> None:
        voter = EnsembleVoter()
        is_fake, score = voter.vote([])
        assert not is_fake
        assert score == 0.0

    def test_threshold_respected(self) -> None:
        voter = EnsembleVoter(threshold=0.8)
        scores = [ModelScore("a", 0.75)]
        is_fake, _ = voter.vote(scores)
        assert not is_fake  # 0.75 < 0.80

    def test_confidence_highest_near_extremes(self) -> None:
        voter = EnsembleVoter(threshold=0.5)
        conf_clear = voter.confidence(0.95)
        conf_uncertain = voter.confidence(0.5)
        assert conf_clear > conf_uncertain


class TestDeepfakeDetectorInit:
    def test_default_init(self) -> None:
        detector = DeepfakeDetector()
        assert detector._threshold == 0.5
        assert detector._sample_frames == 30
        assert detector._allow_experimental is False

    def test_custom_threshold(self) -> None:
        detector = DeepfakeDetector(threshold=0.7)
        assert detector._threshold == 0.7

    def test_no_detector_is_marked_validated(self) -> None:
        """Nothing here has a labelled evaluation, so nothing may claim to be validated."""
        assert VALIDATED_DETECTORS == frozenset()


class TestDeepfakeDetectorResult:
    def test_result_to_dict_structure(self) -> None:
        result = DeepfakeResult(
            media_path="test.jpg",
            is_fake=True,
            confidence=0.85,
            ensemble_score=0.92,
            model_scores={"heuristic": 0.90},
        )
        d = result.to_dict()
        assert d["media_path"] == "test.jpg"
        assert d["is_fake"] is True
        assert "confidence" in d
        assert "ensemble_score" in d
        assert "model_scores" in d

    def test_result_is_experimental_and_unvalidated_by_default(self) -> None:
        d = DeepfakeResult(
            media_path="x", is_fake=False, confidence=0.1, ensemble_score=0.1
        ).to_dict()
        assert d["validated"] is False
        assert d["experimental"] is True
        assert d["limitations"] == EXPERIMENTAL_NOTICE
        assert d["method_detected"] == "unclassified"

    def test_result_scores_rounded(self) -> None:
        result = DeepfakeResult(
            media_path="x",
            is_fake=False,
            confidence=0.123456789,
            ensemble_score=0.123456789,
        )
        assert result.to_dict()["confidence"] == pytest.approx(0.1235, abs=0.0001)

    def test_result_immutable(self) -> None:
        result = DeepfakeResult(media_path="x", is_fake=False, confidence=0.1, ensemble_score=0.1)
        with pytest.raises(AttributeError):
            result.is_fake = True  # type: ignore[misc]


def _flat() -> np.ndarray:
    return np.full((64, 64, 3), 128, dtype=np.uint8)


def _noisy() -> np.ndarray:
    rng = np.random.default_rng(1234)
    return rng.integers(0, 256, (64, 64, 3), dtype=np.uint8)


class TestExperimentalOptIn:
    """An unvalidated detector must not hand out verdicts unless explicitly asked."""

    def test_detect_array_requires_opt_in(self) -> None:
        with pytest.raises(DetectorNotValidatedError):
            DeepfakeDetector().detect_array(_flat())

    @pytest.mark.asyncio
    async def test_detect_image_requires_opt_in(self, tmp_path: Path) -> None:
        with pytest.raises(DetectorNotValidatedError):
            await DeepfakeDetector().detect_image(tmp_path / "x.jpg")

    @pytest.mark.asyncio
    async def test_detect_video_requires_opt_in(self, tmp_path: Path) -> None:
        with pytest.raises(DetectorNotValidatedError):
            await DeepfakeDetector().detect_video(tmp_path / "x.mp4")


class TestHeuristicIsDeterministicAndInputDependent:
    """The previous implementation scored random noise; scores must follow the pixels."""

    def test_same_pixels_give_identical_results(self) -> None:
        detector = DeepfakeDetector(allow_experimental=True)
        first = detector.detect_array(_noisy())
        second = detector.detect_array(_noisy())
        assert first == second

    def test_score_depends_on_the_input(self) -> None:
        detector = DeepfakeDetector(allow_experimental=True)
        flat = detector.detect_array(_flat())
        noisy = detector.detect_array(_noisy())
        assert flat.ensemble_score != noisy.ensemble_score
        assert flat.ensemble_score < noisy.ensemble_score

    def test_result_declares_itself_experimental(self) -> None:
        result = DeepfakeDetector(allow_experimental=True).detect_array(_noisy())
        assert result.validated is False
        assert result.experimental is True
        assert 0.0 <= result.ensemble_score <= 1.0

    def test_empty_array_is_rejected_not_scored(self) -> None:
        with pytest.raises(UnreadableMediaError):
            DeepfakeDetector(allow_experimental=True).detect_array(np.zeros((0, 0, 3)))


class TestMediaDecoding:
    @pytest.mark.asyncio
    async def test_unreadable_image_is_never_scored(self, tmp_path: Path) -> None:
        bad = tmp_path / "not-an-image.jpg"
        bad.write_bytes(b"\x00" * 128)
        detector = DeepfakeDetector(allow_experimental=True)
        with pytest.raises((UnreadableMediaError, DetectorUnavailableError)):
            await detector.detect_image(bad)

    @pytest.mark.asyncio
    async def test_unreadable_video_is_never_reported_authentic(self, tmp_path: Path) -> None:
        bad = tmp_path / "not-a-video.mp4"
        bad.write_bytes(b"\x00" * 1024)
        detector = DeepfakeDetector(sample_frames=10, allow_experimental=True)
        with pytest.raises((UnreadableMediaError, DetectorUnavailableError)):
            await detector.detect_video(bad, sample_frames=10)

    @pytest.mark.asyncio
    async def test_missing_decoder_fails_explicitly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(detector_module, "_PIL_AVAILABLE", False)
        monkeypatch.setattr(detector_module, "_CV2_AVAILABLE", False)
        detector = DeepfakeDetector(allow_experimental=True)
        with pytest.raises(DetectorUnavailableError):
            await detector.detect_image(tmp_path / "x.jpg")
        with pytest.raises(DetectorUnavailableError):
            await detector.detect_video(tmp_path / "x.mp4")


class _StubCapture:
    """A decoder double: ``readable`` is the set of read() call numbers that return a frame."""

    readable: frozenset[int] = frozenset()

    def __init__(self, _path: str) -> None:
        self.reads = 0

    def isOpened(self) -> bool:  # noqa: N802 (OpenCV's name)
        return True

    def get(self, _prop: int) -> int:
        return 4

    def set(self, _prop: int, _idx: int) -> None:
        return None

    def read(self) -> tuple[bool, np.ndarray | None]:
        self.reads += 1
        if self.reads in self.readable:
            return True, np.full((32, 32, 3), 128, dtype=np.uint8)
        return False, None

    def release(self) -> None:
        return None


def _stub_cv2(monkeypatch: pytest.MonkeyPatch, readable: frozenset[int]) -> None:
    """Exercise the frame-sampling path without OpenCV (adapted from PR #181)."""
    import types

    capture = type("Capture", (_StubCapture,), {"readable": readable})
    fake = types.SimpleNamespace(
        VideoCapture=capture,
        CAP_PROP_FRAME_COUNT=7,
        CAP_PROP_POS_FRAMES=1,
        COLOR_BGR2RGB=4,
        cvtColor=lambda frame, _code: frame[..., ::-1],
    )
    monkeypatch.setattr(detector_module, "_CV2_AVAILABLE", True)
    monkeypatch.setattr(detector_module, "cv2", fake, raising=False)


class TestVideoSamplingPath:
    @pytest.mark.asyncio
    async def test_dropped_frames_are_skipped_and_the_rest_aggregated(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_cv2(monkeypatch, frozenset({2, 3, 4}))  # the first read fails
        clip = tmp_path / "clip.mp4"
        clip.write_bytes(b"\x00" * 16)
        result = await DeepfakeDetector(allow_experimental=True).detect_video(clip, sample_frames=4)
        assert result.metadata["frames_sampled"] == 3
        assert sum(result.frame_distribution.values()) == 3
        assert result.validated is False and result.experimental is True

    @pytest.mark.asyncio
    async def test_a_video_with_no_decodable_frame_raises_instead_of_reporting_authentic(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # PR #181 asserted is_fake=False here. An undecodable video is *unknown*, never real.
        _stub_cv2(monkeypatch, frozenset())
        clip = tmp_path / "clip.mp4"
        clip.write_bytes(b"\x00" * 16)
        with pytest.raises(UnreadableMediaError):
            await DeepfakeDetector(allow_experimental=True).detect_video(clip, sample_frames=2)
