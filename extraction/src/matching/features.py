"""Phase 8 — feature engineering for caption matching (plan.md §14).

One dict of named features per `(image, candidate)` pair — lightweight,
deterministic, no model. Every value lies in `0..1` (higher = more
caption-like) and lands in `candidate.features`, so Phase 9's scorer and any
later tuning can see exactly *why* a candidate won.

Feature map (§14.x → feature name):

    §14.1 vertical distance      → `proximity`
    §14.2 horizontal alignment   → `alignment`
    §14.3 horizontal overlap     → `overlap`
    §14.4 relative position      → `position`   (below favored, above secondary)
    §14.5 caption keywords       → `keyword`    (never required — a feature only)
    §14.6 caption length         → `text_shape` (weak signal, no hard cap)
    §14.7 numbering              → `numbering`
    (extra)  sub-figure label    → `sublabel`   (e.g. `(a)` — demoted later)
    §14.8 font/style signals     → deliberately skipped: would require font
      metadata plumbing through TextRegion for marginal gain on NCERT, where
      captions are identified robustly by numbering/position (plan: "do not
      spend significant time reverse-engineering fonts").

Patterns below were mined from the three fixture chapters — every true
NCERT caption block starts with `Fig`, in four formatting variants
(`Fig. 5.6:`, `Fig.12.13:`, `Fig 12.12:`, bare `Fig. 1.3`); sub-labels are
exactly `(a)` / `(b)`; common noise blocks start with `Activity ___` /
`Exercises`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from src.models import BBox, CaptionCandidate, ImageOccurrence
from src.ocr.layout import CAPTION_LABELS

__all__ = [
    "FEATURE_CONFIG",
    "FEATURE_NAMES",
    "FeatureConfig",
    "annotate_candidate",
    "annotate_candidates",
    "compute_features",
]

#: All feature names produced by `compute_features` (fixed contract for §15 weights).
FEATURE_NAMES = (
    "proximity",
    "alignment",
    "overlap",
    "position",
    "keyword",
    "numbering",
    "sublabel",
    "text_shape",
)

_KEYWORD_START_RE = re.compile(r"^\s*(fig|figure|image|plate|diagram)\b", re.IGNORECASE)
_KEYWORD_ANY_RE = re.compile(r"\b(fig|figure|image|plate|diagram)\b", re.IGNORECASE)

#: `Fig. 5.6`, `Figure 12.13`, `Fig.12.13:`, `Fig 12.12` — chapter.number at start.
_NUMBERING_STRONG_RE = re.compile(r"^\s*fig(?:ure)?\.?\s*\d{1,2}\s*\.\s*\d{1,2}", re.IGNORECASE)
#: `Fig. 1` — bare figure number at start.
_NUMBERING_WEAK_RE = re.compile(r"^\s*fig(?:ure)?\.?\s*\d{1,2}\b", re.IGNORECASE)
#: `... in Fig. 12.8 ...` — mid-text reference (e.g. body text pointing at a figure).
_NUMBERING_MENTION_RE = re.compile(r"\bfig(?:ure)?\.?\s*\d{1,2}(?:\.\d{1,2})?", re.IGNORECASE)

#: Standalone sub-figure labels: `(a)`, `(b)`, `(ii)`, `(iv)`.
_SUBLABEL_RE = re.compile(r"^\s*\([a-z0-9ivx]{1,4}\)\s*:?\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class FeatureConfig:
    """Tuning knobs for the §14 features (shared with §15 weighting)."""

    #: Below-window used for proximity decay (mirrors
    #: CandidateConfig.max_below_gap_pt).
    below_window_pt: float = 100.0
    #: Above-window used for proximity decay (mirrors
    #: CandidateConfig.max_above_gap_pt — tightened §33; the fallback
    #: config overrides this from FALLBACK_CANDIDATE_CONFIG).
    above_window_pt: float = 60.0
    #: x-center delta that maps alignment to 0.
    align_max_delta_pt: float = 150.0
    #: §14.4 position scores.
    position_below: float = 1.0
    position_above: float = 0.35
    #: §14.6 text shape: ideal caption length band and decay behavior.
    shape_ideal_min_chars: int = 10
    shape_ideal_max_chars: int = 200
    shape_short_floor: float = 0.35
    shape_decay_chars: int = 400  # linear decay reach beyond the ideal band
    shape_max_ideal_lines: int = 3
    shape_min_lines: int = 7
    #: Final plan §11: a candidate block sitting inside a PP-DocLayout-S
    #: `figure_title` region is strong layout evidence of a caption — the
    #: §15 layout bucket never scores below this for such blocks.
    layout_caption_floor: float = 0.95


#: Default configuration (NCERT-tuned).
FEATURE_CONFIG = FeatureConfig()


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _proximity(image_bbox: BBox, region_bbox: BBox, cfg: FeatureConfig) -> float:
    """§14.1 — small vertical gap scores high (per-window normalized)."""
    gap = image_bbox.vertical_gap(region_bbox)
    if region_bbox.is_below(image_bbox):
        window = cfg.below_window_pt
    else:
        window = cfg.above_window_pt
    return _clamp01(1.0 - gap / window)


def _alignment(image_bbox: BBox, region_bbox: BBox, cfg: FeatureConfig) -> float:
    """§14.2 — 1.0 when centers align, 0.0 at `align_max_delta_pt` apart."""
    delta = abs(image_bbox.x_center - region_bbox.x_center)
    return _clamp01(1.0 - delta / cfg.align_max_delta_pt)


def _keyword(text: str) -> float:
    """§14.5 — keyword at the start is a strong signal, mid-text weaker."""
    if _KEYWORD_START_RE.match(text):
        return 1.0
    if _KEYWORD_ANY_RE.search(text):
        return 0.6
    return 0.0


def _numbering(text: str) -> float:
    """§14.7 — strength of figure numbering evidence."""
    if _NUMBERING_STRONG_RE.match(text):
        return 1.0
    if _NUMBERING_WEAK_RE.match(text):
        return 0.7
    if _NUMBERING_MENTION_RE.search(text):
        return 0.4  # body text referencing a figure
    return 0.0


def _sublabel(text: str) -> float:
    """1.0 for standalone sub-figure labels (`(a)`, `(ii)`) — demoted later."""
    return 1.0 if _SUBLABEL_RE.match(text) else 0.0


def _text_shape(text: str, cfg: FeatureConfig) -> float:
    """§14.6 — captions are short; a weak signal, never a hard cap."""
    length = len(text.strip())
    if length < cfg.shape_ideal_min_chars:
        char_score = cfg.shape_short_floor
    elif length <= cfg.shape_ideal_max_chars:
        char_score = 1.0
    else:
        overflow = length - cfg.shape_ideal_max_chars
        char_score = _clamp01(1.0 - overflow / cfg.shape_decay_chars)

    lines = text.count("\n") + 1
    if lines <= cfg.shape_max_ideal_lines:
        line_score = 1.0
    elif lines >= cfg.shape_min_lines:
        line_score = 0.0
    else:
        span = cfg.shape_min_lines - cfg.shape_max_ideal_lines
        line_score = 1.0 - (lines - cfg.shape_max_ideal_lines) / span

    return _clamp01(min(char_score, line_score))


def compute_features(
    image_bbox: BBox,
    region_bbox: BBox,
    text: str,
    cfg: FeatureConfig = FEATURE_CONFIG,
) -> dict[str, float]:
    """All §14 features for one `(image, text region)` pair."""
    if region_bbox.is_below(image_bbox):
        position = cfg.position_below
    else:
        position = cfg.position_above
    return {
        "proximity": _proximity(image_bbox, region_bbox, cfg),
        "alignment": _alignment(image_bbox, region_bbox, cfg),
        "overlap": _clamp01(image_bbox.horizontal_overlap_ratio(region_bbox)),
        "position": position,
        "keyword": _keyword(text),
        "numbering": _numbering(text),
        "sublabel": _sublabel(text),
        "text_shape": _text_shape(text, cfg),
    }


def annotate_candidate(
    image: ImageOccurrence,
    candidate: CaptionCandidate,
    cfg: FeatureConfig = FEATURE_CONFIG,
) -> CaptionCandidate:
    """Fill `candidate.features` in place (mutates and returns it)."""
    if image.bbox is None:
        raise ValueError(f"image {image.image_id} has no bbox — cannot compute features")
    features = compute_features(image.bbox, candidate.bbox, candidate.text, cfg)
    if candidate.layout_label in CAPTION_LABELS:
        # PP-DocLayout-S says this block IS a caption region (final plan §11):
        # the flag floors the §15 layout bucket in the scorer.
        features["layout_caption"] = 1.0
    candidate.features = features
    return candidate


def annotate_candidates(
    image: ImageOccurrence,
    candidates: Sequence[CaptionCandidate],
    cfg: FeatureConfig = FEATURE_CONFIG,
) -> list[CaptionCandidate]:
    """Annotate every candidate of one image."""
    return [annotate_candidate(image, candidate, cfg) for candidate in candidates]
