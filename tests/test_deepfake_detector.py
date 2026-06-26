from __future__ import annotations

from pathlib import Path

import pytest

from privacylabel.deepfake.detector import DeepfakeDetector, DeepfakeResult
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
        assert not detector._loaded

    def test_custom_threshold(self) -> None:
        detector = DeepfakeDetector(threshold=0.7)
        assert detector._threshold == 0.7


class TestDeepfakeDetectorResult:
    def test_result_to_dict_structure(self) -> None:
        result = DeepfakeResult(
            media_path="test.jpg",
            is_fake=True,
            confidence=0.85,
            ensemble_score=0.92,
            model_scores={"xception": 0.90, "efficientnet": 0.94},
        )
        d = result.to_dict()
        assert d["media_path"] == "test.jpg"
        assert d["is_fake"] is True
        assert "confidence" in d
        assert "ensemble_score" in d
        assert "model_scores" in d

    def test_result_scores_rounded(self) -> None:
        result = DeepfakeResult(
            media_path="x",
            is_fake=False,
            confidence=0.123456789,
            ensemble_score=0.123456789,
        )
        d = result.to_dict()
        assert d["confidence"] == pytest.approx(0.1235, abs=0.0001)

    def test_result_immutable(self) -> None:
        result = DeepfakeResult(
            media_path="x",
            is_fake=False,
            confidence=0.1,
            ensemble_score=0.1,
        )
        with pytest.raises(AttributeError):
            result.is_fake = True  # type: ignore[misc]


class TestDeepfakeDetectorImageAsync:
    @pytest.mark.asyncio
    async def test_detect_returns_deepfake_result(self, tmp_path: Path) -> None:
        # Create a minimal fake image file
        img_path = tmp_path / "test.jpg"
        # Write a 1-pixel JPEG-like binary (detector falls back to mock if torch absent)
        try:
            import io

            from PIL import Image as PILImage
            img = PILImage.new("RGB", (224, 224), color=(100, 150, 200))
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            img_path.write_bytes(buf.getvalue())
        except ImportError:
            img_path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        detector = DeepfakeDetector()
        result = await detector.detect_image(str(img_path))
        assert isinstance(result, DeepfakeResult)
        assert result.media_path == str(img_path)
        assert 0.0 <= result.ensemble_score <= 1.0
        assert 0.0 <= result.confidence

    @pytest.mark.asyncio
    async def test_detect_result_has_model_scores(self, tmp_path: Path) -> None:
        img_path = tmp_path / "test2.jpg"
        try:
            import io

            from PIL import Image as PILImage
            img = PILImage.new("RGB", (224, 224))
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            img_path.write_bytes(buf.getvalue())
        except ImportError:
            img_path.write_bytes(b"\xff\xd8\xff" + b"\x00" * 50)

        detector = DeepfakeDetector()
        result = await detector.detect_image(str(img_path))
        assert len(result.model_scores) >= 1

    @pytest.mark.asyncio
    async def test_detect_video_frame_distribution(self, tmp_path: Path) -> None:
        """Video detection without cv2 returns a synthesised result."""
        video_path = tmp_path / "fake.mp4"
        video_path.write_bytes(b"\x00" * 1024)  # dummy file

        detector = DeepfakeDetector(sample_frames=10)
        result = await detector.detect_video(str(video_path), sample_frames=10)
        assert isinstance(result, DeepfakeResult)
        assert "frames_sampled" in result.metadata
        assert isinstance(result.frame_distribution, dict)


class TestClassifyMethod:
    def test_high_score_is_face_swap(self) -> None:
        detector = DeepfakeDetector()
        method = detector._classify_method({"model": 0.85})
        assert method == "face_swap"

    def test_moderate_score_is_expression_synthesis(self) -> None:
        detector = DeepfakeDetector()
        method = detector._classify_method({"model": 0.65})
        assert method == "expression_synthesis"

    def test_low_score_is_likely_authentic(self) -> None:
        detector = DeepfakeDetector()
        method = detector._classify_method({"model": 0.2})
        assert method == "likely_authentic"

    def test_empty_scores_is_unknown(self) -> None:
        detector = DeepfakeDetector()
        method = detector._classify_method({})
        assert method == "unknown"
