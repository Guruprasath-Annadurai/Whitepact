from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def compute_pairwise_divergence(
    texts: list[str],
) -> tuple[float, dict[tuple[int, int], float]]:
    """
    Pairwise TF-IDF cosine divergence between texts.

    Returns:
        mean_divergence: float in [0.0, 1.0]
        pair_scores: {(i, j): divergence} for all i < j pairs
    """
    if len(texts) < 2:
        return 0.0, {}

    vectorizer = TfidfVectorizer(
        stop_words="english",
        min_df=1,
        ngram_range=(1, 2),
        sublinear_tf=True,
    )
    try:
        tfidf_matrix = vectorizer.fit_transform(texts)
    except ValueError:
        return 0.0, {}

    sim_matrix = cosine_similarity(tfidf_matrix)
    n = len(texts)
    pair_scores: dict[tuple[int, int], float] = {}

    for i in range(n):
        for j in range(i + 1, n):
            pair_scores[(i, j)] = float(1.0 - sim_matrix[i, j])

    mean = float(np.mean(list(pair_scores.values()))) if pair_scores else 0.0
    return mean, pair_scores


def compute_length_ratio_score(responses: list[str]) -> float:
    """
    Penalise significant length asymmetry between responses.
    A 2x length difference contributes ~0.10; capped at 0.20.
    """
    lengths = [len(r.split()) for r in responses if r.strip()]
    if len(lengths) < 2 or max(lengths) == 0:
        return 0.0
    ratio = max(lengths) / max(min(lengths), 1)
    return float(np.clip((ratio - 1.0) / 10.0, 0.0, 0.2))


def compute_sentiment_divergence(texts: list[str]) -> float:
    """
    Measure tone divergence using VADER compound sentiment scores.

    Detects cases where vocabulary is similar but valence shifts —
    e.g. "assertive" vs "aggressive" for the same scenario.

    Returns 0.0 (same tone) to 1.0 (extreme tone difference).
    Falls back gracefully to 0.0 if nltk is not installed.
    """
    if len(texts) < 2:
        return 0.0

    sia = _get_vader()
    if sia is None:
        return 0.0

    # compound is in [-1, 1]; max pairwise distance is 2
    scores = [sia.polarity_scores(t)["compound"] for t in texts]
    diffs: list[float] = []
    for i in range(len(scores)):
        for j in range(i + 1, len(scores)):
            diffs.append(abs(scores[i] - scores[j]) / 2.0)

    return float(np.mean(diffs)) if diffs else 0.0


def compute_combined_score(
    texts: list[str],
    *,
    sentiment_weight: float = 0.20,
) -> tuple[float, dict[tuple[int, int], float]]:
    """
    Combine TF-IDF divergence, length asymmetry, and sentiment divergence
    into a single bias score in [0.0, 1.0].

    Weights: semantic + length = 80%, sentiment = 20%.
    """
    semantic_score, pair_scores = compute_pairwise_divergence(texts)
    length_score = compute_length_ratio_score(texts)
    sentiment_score = compute_sentiment_divergence(texts)

    combined = float(np.clip(
        (1.0 - sentiment_weight) * (semantic_score + length_score)
        + sentiment_weight * sentiment_score,
        0.0,
        1.0,
    ))
    return combined, pair_scores


def bootstrap_confidence_interval(
    scores: list[float],
    *,
    n_bootstrap: int = 1000,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """
    Bootstrap confidence interval for a list of per-template scores.

    With only a handful of templates the interval will be wide — that's
    correct; it tells the user they need more data to be confident.

    Returns:
        (lower_bound, upper_bound) at the given confidence level.
    """
    if len(scores) == 0:
        return (0.0, 0.0)
    if len(scores) == 1:
        return (scores[0], scores[0])

    rng = np.random.default_rng(42)
    arr = np.array(scores, dtype=float)
    resampled_means = [
        float(np.mean(rng.choice(arr, size=len(arr), replace=True)))
        for _ in range(n_bootstrap)
    ]
    alpha = (1.0 - confidence) / 2.0
    lower = float(np.percentile(resampled_means, alpha * 100))
    upper = float(np.percentile(resampled_means, (1.0 - alpha) * 100))
    return (lower, upper)


def _get_vader():  # type: ignore[return]
    """Return a VADER SentimentIntensityAnalyzer, downloading lexicon if needed.

    nltk is an opt-in extra (`pip install rai-governance-platform[sentiment]`),
    not a default dependency — see pyproject.toml for why (PYSEC-2026-597).
    Returns None if it isn't installed; callers already treat that as "no
    sentiment signal available" rather than an error.
    """
    try:
        from nltk.sentiment.vader import SentimentIntensityAnalyzer

        try:
            return SentimentIntensityAnalyzer()
        except LookupError:
            import nltk

            nltk.download("vader_lexicon", quiet=True)
            return SentimentIntensityAnalyzer()
    except ImportError:
        return None
