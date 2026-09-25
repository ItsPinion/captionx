"""Phase 9 — primary scoring function (plan.md §15).

Combines the §14 features into one caption-likelihood score per candidate:

    candidate_score =
        proximity + alignment + keyword + numbering + text_shape + layout

with the plan's example weighting (§15 — "starting points, not permanent
truths", retune in Phase 32):

    proximity         40%
    horizontal align  20%
    caption keywords  15%
    numbering         10%
    text shape        10%
    layout             5%    (= position and overlap, averaged)

plus one guard the fixture data demanded: standalone sub-figure labels
(`(a)`, `(ii)`) are demoted multiplicatively — they describe part of a
figure, never the figure, yet otherwise score well on proximity alone.

The score is a weighted *sum* of 0..1 features, so it also lies in 0..1.
Ranking only happens here; accept/reject decisions belong to the confidence
stage (Phase 10) and the fallback logic (Phase 11).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from src.models import CaptionCandidate

from .features import FEATURE_CONFIG  # noqa: F401  (re-exported tuning config)

__all__ = ["SCORE_CONFIG", "ScoreConfig", "layout_feature", "score_candidate", "score_candidates", "rank_candidates"]


@dataclass(frozen=True)
class ScoreConfig:
    """§15 weights (must sum to 1.0) + guards. Tune on NCERT output in Phase 32."""

    proximity: float = 0.40
    alignment: float = 0.20
    keyword: float = 0.15
    numbering: float = 0.10
    text_shape: float = 0.10
    layout: float = 0.05
    #: Final score is multiplied by `(1 - demotion * sublabel)`.
    sublabel_demotion: float = 0.45
    #: Blend of `position` and `overlap` forming the §15 "layout" bucket.
    layout_position_share: float = 0.5


#: Default configuration (plan §15 example weighting, NCERT-tuned).
SCORE_CONFIG = ScoreConfig()


def layout_feature(features: dict[str, float], cfg: ScoreConfig = SCORE_CONFIG) -> float:
    """The §15 layout bucket: relative position blended with horizontal overlap.

    Final plan §11: PP-DocLayout-S `figure_title` evidence (flagged as
    `layout_caption` by the feature stage) floors this bucket — a detected
    caption region is stronger layout signal than geometry alone.
    """
    share = cfg.layout_position_share
    blend = share * features["position"] + (1.0 - share) * features["overlap"]
    if features.get("layout_caption"):
        return max(blend, 0.95)
    return blend


def score_candidate(
    candidate: CaptionCandidate,
    cfg: ScoreConfig = SCORE_CONFIG,
    feature_cfg: FeatureConfig = FEATURE_CONFIG,
) -> float:
    """Compute and store `candidate.score` (mutates and returns the score).

    Raises `ValueError` if the candidate has not been annotated with §14
    features yet (`annotate_candidates`).
    """
    features = candidate.features
    missing = [name for name in feature_cfg and _WEIGHT_KEYS(cfg) if name not in features]
    if missing:
        raise ValueError(
            f"candidate {candidate.image_id!r} is missing features {missing} — "
            "run annotate_candidates() before scoring"
        )

    score = (
        cfg.proximity * features["proximity"]
        + cfg.alignment * features["alignment"]
        + cfg.keyword * features["keyword"]
        + cfg.numbering * features["numbering"]
        + cfg.text_shape * features["text_shape"]
        + cfg.layout * layout_feature(features, cfg)
    )
    score *= 1.0 - cfg.sublabel_demotion * features["sublabel"]
    candidate.score = max(0.0, min(1.0, score))
    return candidate.score


def _WEIGHT_KEYS(cfg: ScoreConfig) -> tuple[str, ...]:
    return ("proximity", "alignment", "keyword", "numbering", "text_shape", "position", "overlap", "sublabel")


def score_candidates(
    candidates: Sequence[CaptionCandidate],
    cfg: ScoreConfig = SCORE_CONFIG,
) -> list[float]:
    """Score every candidate in place; returns the scores in input order."""
    return [score_candidate(candidate, cfg) for candidate in candidates]


def rank_candidates(
    candidates: Sequence[CaptionCandidate],
) -> list[CaptionCandidate]:
    """Candidates sorted by score, best first (input list not mutated)."""
    return sorted(candidates, key=lambda c: c.score, reverse=True)
