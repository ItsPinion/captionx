"""Document-level matching orchestration (plan.md §17 final rule).

Runs the two-pass strategy over a `DocumentExtraction` and produces the
final per-image `MatchResult`s:

    strict pass  (§13–§16): tight windows, plan-§15 weights
        ↓ unresolved images only
    fallback pass (§17):    broadened windows, boosted keyword/numbering
        ↓ still-unmatched figures directly above a series winner
    series passthrough (§17 / stacked NCERT figures)
        ↓ anything left
    caption_not_found (§2.4: never invent)

Method labeling (§13): strict matches → `native_text` / `ocr` by candidate
source; fallback and passthrough matches → `fallback`; unresolved →
`no_reliable_candidate`.
"""

from __future__ import annotations

from src.models import (
    CaptionCandidate,
    ImageOccurrence,
    MatchMethod,
    MatchResult,
    MatchStatus,
    TextSource,
)
from src.pdf.extractor import DocumentExtraction

from .candidates import (
    CANDIDATE_CONFIG,
    CandidateConfig,
    collect_candidates,
)
from .confidence import (
    CONFIDENCE_CONFIG,
    ConfidenceConfig,
    evaluate_top_candidate,
)
from .fallback import (
    FALLBACK_CANDIDATE_CONFIG,
    FALLBACK_CONFIDENCE_CONFIG,
    FALLBACK_FEATURE_CONFIG,
    FALLBACK_SCORE_CONFIG,
    series_passthrough,
)
from .features import (
    FEATURE_CONFIG,
    FeatureConfig,
    annotate_candidates,
)
from .scorer import SCORE_CONFIG, ScoreConfig, rank_candidates, score_candidates

__all__ = ["match_document", "match_image"]

_METHOD_BY_SOURCE = {
    TextSource.NATIVE_PDF: MatchMethod.NATIVE_TEXT,
    TextSource.OCR: MatchMethod.OCR,
}


def _best_of(
    image: ImageOccurrence,
    regions,
    page_height: float,
    candidate_cfg: CandidateConfig,
    feature_cfg: FeatureConfig,
    score_cfg: ScoreConfig,
    confidence_cfg: ConfidenceConfig,
):
    """One pass: candidates → features → scores → (best, confidence, accepted)."""
    candidates: list[CaptionCandidate] = collect_candidates(
        image, regions, page_height=page_height, cfg=candidate_cfg
    )
    annotate_candidates(image, candidates, feature_cfg)
    score_candidates(candidates, score_cfg)
    ranked = rank_candidates(candidates)
    return evaluate_top_candidate(ranked, confidence_cfg)


def match_image(image, regions, page_height: float):
    """Strict pass then fallback pass for one image → MatchResult."""
    best, confidence, accepted = _best_of(
        image,
        regions,
        page_height,
        CANDIDATE_CONFIG,
        FEATURE_CONFIG,
        SCORE_CONFIG,
        CONFIDENCE_CONFIG,
    )
    if accepted and best is not None:
        return MatchResult(
            image_id=image.image_id,
            caption=best.text,
            confidence=confidence or 0.0,
            status=MatchStatus.MATCHED,
            method=_METHOD_BY_SOURCE[best.source],
        )

    best, confidence, accepted = _best_of(
        image,
        regions,
        page_height,
        FALLBACK_CANDIDATE_CONFIG,
        FALLBACK_FEATURE_CONFIG,
        FALLBACK_SCORE_CONFIG,
        FALLBACK_CONFIDENCE_CONFIG,
    )
    if accepted and best is not None:
        return MatchResult(
            image_id=image.image_id,
            caption=best.text,
            confidence=confidence or 0.0,
            status=MatchStatus.MATCHED,
            method=MatchMethod.FALLBACK,
        )

    # §17 final rule: nothing exceeded the minimum confidence.
    return MatchResult(
        image_id=image.image_id,
        caption=None,
        confidence=round(confidence, 4) if confidence is not None else 0.0,
        status=MatchStatus.CAPTION_NOT_FOUND,
        method=MatchMethod.NO_RELIABLE_CANDIDATE,
    )


def match_document(document: DocumentExtraction) -> dict[str, MatchResult]:
    """Final `MatchResult` per image occurrence of the document."""
    results: dict[str, MatchResult] = {}
    figures = document.figures

    for page in document.pages:
        for figure in page.figures:
            results[figure.occurrence.image_id] = match_image(
                figure.occurrence,
                page.text_regions,
                page_height=page.page_height or 842.0,
            )

    series_passthrough(figures, results)
    return results
