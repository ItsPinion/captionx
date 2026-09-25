"""Phase 10 — confidence calculation (plan.md §16).

Exposes how certain a mapping is, from the ranked candidate scores:

    confidence = w_score · top_score + w_margin · margin_ratio
    margin_ratio = (top - second) / top

A mapping is *accepted* only when all of the following hold:

1. `top_score ≥ min_score` — the best candidate must be reasonably strong;
2. `confidence ≥ min_confidence` — the plan's "clearly good / probably good /
   uncertain" split (§16); the confidence value itself is surfaced to the UI;
3. evidence gate — the winner shows real *caption* evidence
   (`max(keyword, numbering) ≥ strong_evidence`, i.e. a `Fig…` start or bare
   `Fig. N`) **or** the score is high enough to stand alone without keywords
   (`≥ no_keyword_escape`), for the rare caption without figure keywords.
   §2.4: a false mapping is worse than `caption_not_found` — body text and
   sub-labels must never win on geometry alone.

Calibration notes (measured on the fixtures):
- body-text profiles top out around `score ≈ 0.67` (no keyword/numbering) —
  the evidence gate rejects them;
- geometry-only winners like `(1879-1955)` reach `≈ 0.66` — also rejected by
  the evidence gate (a date under a portrait is not a caption);
- geometry-only winners cap at `0.75`, below the escape — the strict matcher
  cannot accept a captionless figure's ambient text. (True keyword-less
  captions are equally rejected — they do not occur in the target chapters;
  every measured NCERT caption starts with `Fig`.)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from src.models import CaptionCandidate

from .scorer import rank_candidates

__all__ = [
    "CONFIDENCE_CONFIG",
    "ConfidenceConfig",
    "caption_evidence",
    "evaluate_top_candidate",
    "match_confidence",
]


@dataclass(frozen=True)
class ConfidenceConfig:
    """Acceptance thresholds (§16; retune in Phase 32 with real error data)."""

    #: Best-candidate score below this never matches.
    min_score: float = 0.45
    #: Confidence below this never matches.
    min_confidence: float = 0.55
    #: `max(keyword, numbering)` at or above this counts as caption evidence.
    strong_evidence: float = 0.7
    #: Score that would stand on its own without any keyword/numbering
    #: evidence. Set ABOVE the geometry-only maximum (0.40+0.20+0.10+0.05
    #: = 0.75): a block with no figure words can never match on placement
    #: alone — measured trap: `H. R. Hertz` under a portrait scores 0.74.
    no_keyword_escape: float = 0.78
    #: Confidence blend.
    weight_score: float = 0.7
    weight_margin: float = 0.3


#: Default configuration.
CONFIDENCE_CONFIG = ConfidenceConfig()


def caption_evidence(features: dict[str, float]) -> float:
    """Strength of figure-caption evidence carried by a candidate."""
    return max(features.get("keyword", 0.0), features.get("numbering", 0.0))


def match_confidence(
    ranked: Sequence[CaptionCandidate],
    cfg: ConfidenceConfig = CONFIDENCE_CONFIG,
) -> Optional[float]:
    """Confidence for mapping an image to `ranked[0]`, or `None` if empty.

    Blend of absolute score and relative margin over the runner-up (§16):
    `0.7 · top + 0.3 · (top − second) / top`.
    """
    if not ranked:
        return None
    top = ranked[0].score
    if len(ranked) < 2:
        margin_ratio = 1.0
    else:
        second = ranked[1].score
        if top <= 0.0:
            return 0.0
        margin_ratio = (top - second) / top
    confidence = cfg.weight_score * top + cfg.weight_margin * margin_ratio
    return max(0.0, min(1.0, confidence))


def evaluate_top_candidate(
    ranked: Sequence[CaptionCandidate],
    cfg: ConfidenceConfig = CONFIDENCE_CONFIG,
) -> tuple[Optional[CaptionCandidate], Optional[float], bool]:
    """The full Phase 10 verdict for one image.

    Returns `(best_candidate, confidence, accepted)`; `(None, None, False)`
    when there are no candidates at all. Acceptance rules are documented in
    the module docstring; the final `caption_not_found` labeling happens in
    the Phase 11 matcher, which consumes this verdict.
    """
    if not ranked:
        return None, None, False

    best = ranked[0]
    confidence = match_confidence(ranked, cfg)
    assert confidence is not None  # ranked is non-empty

    evidence = caption_evidence(best.features)
    if evidence >= cfg.strong_evidence:
        evidence_ok = True
    elif evidence == 0.0:
        # no figure words anywhere: only a standout score may match
        evidence_ok = best.score >= cfg.no_keyword_escape
    else:
        # mid-text figure mention: body prose describing a figure
        evidence_ok = False

    accepted = (
        best.score >= cfg.min_score
        and confidence >= cfg.min_confidence
        and evidence_ok
    )
    return best, confidence, accepted
