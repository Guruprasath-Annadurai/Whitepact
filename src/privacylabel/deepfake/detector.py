# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""
EXPERIMENTAL media-manipulation signal. This is NOT a validated deepfake detector.

What this module actually does
------------------------------
It computes one deterministic, uncalibrated signal: the variance of the second
spatial derivative of the luminance channel, scaled into [0, 1]. High-frequency
energy is *sometimes* elevated in synthesised or heavily re-encoded images, but the
signal is also elevated by sharp real photographs, text, and compression noise.
It has not been calibrated or evaluated against any labelled dataset, and no false
positive or false negative rate is claimed.

What it deliberately does not do
--------------------------------
* It ships no trained neural network. Earlier revisions built InceptionV3 and
  EfficientNet with ``weights=None`` (random initialisation) and reported their
  softmax output; random weights carry no information about authenticity.
* It never fabricates a score. If media cannot be decoded, it raises instead of
  scoring synthetic noise, and an unreadable video is never reported as "real".
* It does not classify a manipulation method.

Because the signal is unvalidated, every detection call requires an explicit
``allow_experimental=True`` opt-in, every result carries ``validated=False`` and
``experimental=True``, and the result must not be used as independent governance
or trust evidence. Promoting this to a supported detector requires a trained model,
a documented labelled evaluation (dataset scope, versions, error rates), and a
change to ``VALIDATED_DETECTORS`` backed by that record.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from privacylabel.deepfake.ensemble import EnsembleVoter, ModelScore, VotingStrategy

_log = logging.getLogger(__name__)

try:
    from PIL import Image

    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

try:
    import cv2

    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False

# Detector identifiers with a recorded labelled evaluation. Empty on purpose: no
# detector in this repository has one. Never add an entry without that record.
VALIDATED_DETECTORS: frozenset[str] = frozenset()

HEURISTIC_NAME = "uncalibrated_frequency_heuristic"

EXPERIMENTAL_NOTICE = (
    "Experimental, unvalidated frequency heuristic. Not evaluated on any labelled "
    "dataset; error rates unknown. Not independent evidence of authenticity."
)


class DetectorNotValidatedError(RuntimeError):
    """Raised when an unvalidated detector is used without an explicit opt-in."""


class DetectorUnavailableError(RuntimeError):
    """Raised when a required media decoder is not installed."""


class UnreadableMediaError(ValueError):
    """Raised when media cannot be decoded; unreadable media is never scored."""


@dataclass(frozen=True)
class DeepfakeResult:
    """Detection result for a single media asset.

    ``validated`` is False unless the detector appears in ``VALIDATED_DETECTORS``.
    A result with ``validated=False`` is an experimental signal, not evidence.
    """

    media_path: str
    is_fake: bool
    confidence: float  # [0, 1] -- distance of the score from the decision threshold
    ensemble_score: float  # raw fake-probability signal from the ensemble
    model_scores: dict[str, float] = field(default_factory=dict)
    affected_frames: list[int] = field(default_factory=list)
    frame_distribution: dict[str, int] = field(default_factory=dict)
    method_detected: str = "unclassified"
    metadata: dict[str, Any] = field(default_factory=dict)
    validated: bool = False
    experimental: bool = True
    limitations: str = EXPERIMENTAL_NOTICE

    def to_dict(self) -> dict[str, Any]:
        return {
            "media_path": self.media_path,
            "is_fake": self.is_fake,
            "confidence": round(self.confidence, 4),
            "ensemble_score": round(self.ensemble_score, 4),
            "model_scores": {k: round(v, 4) for k, v in self.model_scores.items()},
            "affected_frames": self.affected_frames,
            "frame_distribution": self.frame_distribution,
            "method_detected": self.method_detected,
            "metadata": self.metadata,
            "validated": self.validated,
            "experimental": self.experimental,
            "limitations": self.limitations,
        }


class _FrequencyHeuristic:
    """Deterministic, uncalibrated high-frequency-energy signal. See module docstring."""

    def predict(self, image_array: np.ndarray) -> float:
        if image_array.size == 0:
            raise UnreadableMediaError("Cannot score an empty image array.")
        gray = np.mean(image_array, axis=-1) if image_array.ndim == 3 else image_array
        laplacian_var = float(np.var(np.gradient(np.gradient(gray.astype(float)))))
        return float(min(laplacian_var / 1000.0, 1.0))


class DeepfakeDetector:
    """Experimental media-manipulation signal (see the module docstring).

    Usage::

        detector = DeepfakeDetector(allow_experimental=True)
        result = detector.detect_array(frame)       # already-decoded pixels
        result = await detector.detect_image("photo.jpg")   # needs Pillow or OpenCV
        print(result.validated)  # always False today

    Parameters
    ----------
    strategy : VotingStrategy
        How to combine model scores. Default MEAN.
    threshold : float
        Score threshold for ``is_fake``. Default 0.5. Not calibrated.
    sample_frames : int
        Number of frames to sample from video. Default 30.
    allow_experimental : bool
        Must be True to run. Without it every detection call raises
        ``DetectorNotValidatedError`` instead of returning an unvalidated verdict.
    """

    def __init__(
        self,
        strategy: VotingStrategy = VotingStrategy.MEAN,
        threshold: float = 0.5,
        sample_frames: int = 30,
        *,
        allow_experimental: bool = False,
    ) -> None:
        self._voter = EnsembleVoter(strategy=strategy, threshold=threshold)
        self._threshold = threshold
        self._sample_frames = sample_frames
        self._allow_experimental = allow_experimental
        self._models: dict[str, Any] = {HEURISTIC_NAME: _FrequencyHeuristic()}

    def _require_opt_in(self) -> None:
        if HEURISTIC_NAME in VALIDATED_DETECTORS:
            return
        if not self._allow_experimental:
            raise DetectorNotValidatedError(
                "No validated deepfake detector is available. This module provides only an "
                "experimental, uncalibrated frequency heuristic; pass "
                "allow_experimental=True to use it and treat the result as non-evidence."
            )

    def _score_pixels(self, image: np.ndarray) -> dict[str, float]:
        return {name: model.predict(image) for name, model in self._models.items()}

    def _result_for(
        self,
        media: str,
        model_scores: dict[str, float],
        **extra: Any,
    ) -> DeepfakeResult:
        ensemble_scores = [
            ModelScore(model_name=k, fake_probability=v) for k, v in model_scores.items()
        ]
        is_fake, ensemble_score = self._voter.vote(ensemble_scores)
        return DeepfakeResult(
            media_path=media,
            is_fake=is_fake,
            confidence=self._voter.confidence(ensemble_score),
            ensemble_score=ensemble_score,
            model_scores=model_scores,
            validated=HEURISTIC_NAME in VALIDATED_DETECTORS,
            experimental=HEURISTIC_NAME not in VALIDATED_DETECTORS,
            **extra,
        )

    def detect_array(self, image: np.ndarray, *, label: str = "<array>") -> DeepfakeResult:
        """Score an already-decoded RGB/grayscale pixel array. Deterministic."""
        self._require_opt_in()
        scores = self._score_pixels(np.asarray(image))
        return self._result_for(label, scores, metadata={"models_used": list(scores)})

    @staticmethod
    def _decode_image(path: Path) -> np.ndarray:
        if _PIL_AVAILABLE:
            try:
                with Image.open(path) as handle:
                    return np.asarray(handle.convert("RGB"))
            except Exception as exc:
                raise UnreadableMediaError(f"Cannot decode image {path}: {exc}") from exc
        if _CV2_AVAILABLE:
            frame = cv2.imread(str(path))
            if frame is None:
                raise UnreadableMediaError(f"Cannot decode image {path}")
            return np.asarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        raise DetectorUnavailableError(
            "No image decoder installed. Install with: pip install 'rai-governance-platform[deepfake]'"
        )

    async def detect_image(self, image_path: str | Path) -> DeepfakeResult:
        """Score an image file. Raises rather than scoring anything but the real pixels."""
        self._require_opt_in()
        path = Path(image_path)
        scores = self._score_pixels(self._decode_image(path))
        return self._result_for(str(path), scores, metadata={"models_used": list(scores)})

    async def detect_video(
        self, video_path: str | Path, sample_frames: int | None = None
    ) -> DeepfakeResult:
        """Score uniformly sampled video frames.

        Raises ``DetectorUnavailableError`` without OpenCV and ``UnreadableMediaError``
        when no frame can be decoded; an unreadable video is never reported as real.
        """
        self._require_opt_in()
        if not _CV2_AVAILABLE:
            raise DetectorUnavailableError(
                "No video decoder installed. Install with: "
                "pip install 'rai-governance-platform[deepfake]'"
            )
        path = Path(video_path)
        n_frames = sample_frames or self._sample_frames

        cap = cv2.VideoCapture(str(path))
        try:
            if not cap.isOpened():
                raise UnreadableMediaError(f"Cannot open video {path}")
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or n_frames
            indices = np.linspace(0, max(total - 1, 0), n_frames, dtype=int)
            frame_probs: list[float] = []
            for idx in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
                ret, frame = cap.read()
                if not ret:
                    continue
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame_probs.append(float(np.mean(list(self._score_pixels(rgb).values()))))
        finally:
            cap.release()

        if not frame_probs:
            raise UnreadableMediaError(f"No frames could be decoded from {path}")

        probs = np.array(frame_probs)
        agg = float(np.mean(probs))
        distribution = {
            "real": int(np.sum(probs < 0.4)),
            "uncertain": int(np.sum((probs >= 0.4) & (probs <= 0.6))),
            "fake": int(np.sum(probs > 0.6)),
        }
        return DeepfakeResult(
            media_path=str(path),
            is_fake=agg >= self._threshold,
            confidence=self._voter.confidence(agg),
            ensemble_score=agg,
            model_scores={HEURISTIC_NAME: agg},
            affected_frames=[i for i, p in enumerate(probs) if p >= self._threshold],
            frame_distribution=distribution,
            metadata={"frames_sampled": len(probs)},
            validated=HEURISTIC_NAME in VALIDATED_DETECTORS,
            experimental=HEURISTIC_NAME not in VALIDATED_DETECTORS,
        )
