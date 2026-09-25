"""Phase 11 — fallback matching (plan.md §17).

The primary matcher (Phases 9–10) is deliberately strict: same page, near the
image, strong positional relationship. The fallback matcher is "slightly
broader" (§17):

    same page · larger candidate windows (below 160 pt, above 260 pt)
    · keyword/numbering evidence dominates the score
    · still never searches neighboring pages (§17)

Evidence discipline is unchanged where it matters most (§2.4 — a false
mapping is worse than `caption_not_found`):

- zero figure evidence (`no Fig…` anywhere) can NEVER match — the fallback
  escape score is set above 1.0, so placement alone is never enough;
- mid-text figure *mentions* ("shown in Fig. 12.8 above") still never match;
- only a `Fig…`-starting block (strong evidence) can win.

This module also implements the one case windows cannot reach: NCERT stacked
experiment figures share one series caption under the *bottom* figure
("Fig. 1.6: (a) …, (b) …"). `series_passthrough` offers such a caption to an
unmatched figure directly above its winner.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.models import MatchMethod, MatchResult, MatchStatus

from src.matching.candidates import CandidateConfig, CANDIDATE_CONFIG
from src.matching.confidence import ConfidenceConfig, CONFIDENCE_CONFIG
from src.matching.features import FeatureConfig, FEATURE_CONFIG
from src.matching.scorer import ScoreConfig, SCORE_CONFIG

__all__ = [
    "FALLBACK_CANDIDATE_CONFIG",
    "FALLBACK_CONFIDENCE_CONFIG",
    "FALLBACK_FEATURE_CONFIG",
    "FALLBACK_SCORE_CONFIG",
    "FallbackConfig",
    "FALLBACK_CONFIG",
    "series_passthrough",
]

#: Broader windows for the fallback pass (§17 "larger candidate window").
#: Measured targets: Fig 1.5 at 95 pt below, Fig 12.8 at 138 pt above,
#: Fig 12.12 at 132 pt below — 160/260 covers all with margin.
FALLBACK_CANDIDATE_CONFIG = CandidateConfig(
    max_below_gap_pt=160.0,
    max_above_gap_pt=260.0,
)

#: Proximity decays over the broadened windows, so far captions keep
#: meaningful proximity instead of decaying to zero at 100/150 pt.
FALLBACK_FEATURE_CONFIG = FeatureConfig(
    below_window_pt=FALLBACK_CANDIDATE_CONFIG.max_below_gap_pt,
    above_window_pt=FALLBACK_CANDIDATE_CONFIG.max_above_gap_pt,
)

#: §17 "increase weight of keyword/numbering evidence": textual evidence
#: dominates (0.45 combined) over placement (0.25 proximity + 0.10
#: alignment + 0.10 layout); shape stays a weak 0.10.
FALLBACK_SCORE_CONFIG = ScoreConfig(
    proximity=0.25,
    alignment=0.10,
    keyword=0.25,
    numbering=0.20,
    text_shape=0.10,
    layout=0.10,
)

#: Relaxed thresholds, but the zero-evidence escape is disabled entirely
#: (score 1.1 is unreachable): without figure words there is no match.
FALLBACK_CONFIDENCE_CONFIG = ConfidenceConfig(
    min_score=0.50,
    min_confidence=0.50,
    no_keyword_escape=1.1,
)


@dataclass(frozen=True)
class FallbackConfig:
    """Stacked-series passthrough rules (§17; NCERT-tuned)."""

    #: Vertical gap between the upper figure's bottom and the winner's top.
    max_series_gap_pt: float = 80.0
    #: The pair must share the column.
    min_series_overlap_ratio: float = 0.5
    #: Passthrough confidence shrink vs the winner's confidence.
    confidence_shrink: float = 0.85


#: Default passthrough configuration.
FALLBACK_CONFIG = FallbackConfig()

#: Series captions enumerate their sub-figures: "(a) …, (b) …", "(i)…".
_SERIES_MARKER_RE = re.compile(r"\([a-z0-9]{1,4}\)", re.IGNORECASE)


def series_passthrough(
    figures,  # Sequence[ExtractedFigure-like: .occurrence]
    results,  # dict[image_id, MatchResult] — mutated in place
    cfg: FallbackConfig = FALLBACK_CONFIG,
) -> int:
    """Offer a winner's series caption to an unmatched figure directly above.

    Fires only when ALL hold (measured sole fixture case: Fig 1.6 → the
    upper of two stacked experiment setups, caption 289 pt away):
    - the upper figure has no match after strict + fallback passes;
    - the figure directly below it IS matched, within `max_series_gap_pt`,
      sharing the column (`min_series_overlap_ratio`);
    - the winner's caption carries a series marker ("(a)", "(ii)", …).

    Returns the number of passthrough assignments (mutates `results`).
    """
    assigned = 0
    by_page: dict[int, list] = {}
    for figure in figures:
        if figure.occurrence.bbox is not None:
            by_page.setdefault(figure.occurrence.page, []).append(figure)

    for page_figures in by_page.values():
        ordered = sorted(page_figures, key=lambda f: f.occurrence.bbox.y0)
        for i, upper in enumerate(ordered):
            upper_result = results.get(upper.occurrence.image_id)
            if upper_result is not None and upper_result.status.value == "matched":
                continue
            # nearest matched figure below
            winner = None
            for lower in ordered[i + 1 :]:
                lower_result = results.get(lower.occurrence.image_id)
                if lower_result is None or lower_result.status.value != "matched":
                    continue
                gap = lower.occurrence.bbox.y0 - upper.occurrence.bbox.y1
                overlap = upper.occurrence.bbox.horizontal_overlap_ratio(lower.occurrence.bbox)
                if 0 <= gap <= cfg.max_series_gap_pt and overlap >= cfg.min_series_overlap_ratio:
                    winner = (lower, lower_result)
                break  # only the directly-below figure counts

            if winner is None:
                continue
            lower, lower_result = winner
            caption = lower_result.caption
            if not caption or not _SERIES_MARKER_RE.search(caption):
                continue
            results[upper.occurrence.image_id] = MatchResult(
                image_id=upper.occurrence.image_id,
                caption=caption,
                confidence=min(1.0, lower_result.confidence * cfg.confidence_shrink),
                status=MatchStatus.MATCHED,
                method=MatchMethod.FALLBACK,
            )
            assigned += 1
    return assigned
