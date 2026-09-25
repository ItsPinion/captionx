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
    BBox,
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
    merge_split_captions,
)
from .confidence import (
    CONFIDENCE_CONFIG,
    ConfidenceConfig,
    evaluate_top_candidate,
)
from src.ocr.layout import IMAGE_LABELS
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
    *,
    bbox_override=None,
    page_scan: bool = False,
):
    """One pass: candidates → features → scores → (best, confidence, accepted)."""
    candidates: list[CaptionCandidate] = collect_candidates(
        image,
        regions,
        page_height=page_height,
        cfg=candidate_cfg,
        bbox_override=bbox_override,
        page_scan=page_scan,
    )
    annotate_candidates(image, candidates, feature_cfg)
    score_candidates(candidates, score_cfg)
    ranked = rank_candidates(candidates)
    return evaluate_top_candidate(ranked, confidence_cfg)


def match_image(
    image,
    regions,
    page_height: float,
    *,
    bbox_override=None,
    page_scan: bool = False,
):
    """Strict pass then fallback pass for one image → MatchResult."""
    best, confidence, accepted = _best_of(
        image,
        regions,
        page_height,
        CANDIDATE_CONFIG,
        FEATURE_CONFIG,
        SCORE_CONFIG,
        CONFIDENCE_CONFIG,
        bbox_override=bbox_override,
        page_scan=page_scan,
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
        bbox_override=bbox_override,
        page_scan=page_scan,
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


def _page_scan_context(
    occurrence_bbox, page
) -> tuple[BBox | None, bool]:
    """Effective bbox + page-scan flag for one occurrence (final plan §11).

    A raster covering most of the page is a page scan: every text block sits
    "inside" it, so the matcher uses the best-overlapping PP-DocLayout-S
    figure region as the effective image bbox and disables the
    figure-internal filter. Native multi-figure pages are unaffected.
    """
    if occurrence_bbox is None or page.page_width is None or page.page_height is None:
        return None, False
    page_area = page.page_width * page.page_height
    bbox_area = occurrence_bbox.width * occurrence_bbox.height
    if page_area <= 0 or bbox_area < 0.7 * page_area:
        return None, False
    best = None
    best_ratio = 0.0
    for region in page.layout_regions:
        if region.label not in IMAGE_LABELS:
            continue
        overlap = (
            occurrence_bbox.horizontal_overlap(region.bbox)
            * max(0.0, min(occurrence_bbox.y1, region.bbox.y1) - max(occurrence_bbox.y0, region.bbox.y0))
        )
        ratio = overlap / max(1e-6, region.bbox.width * region.bbox.height)
        if ratio >= 0.5 and ratio > best_ratio:
            best, best_ratio = region.bbox, ratio
    return best, True


def match_document(document: DocumentExtraction) -> dict[str, MatchResult]:
    """Final `MatchResult` per image occurrence of the document."""
    results: dict[str, MatchResult] = {}
    figures = document.figures

    for page in document.pages:
        # §38 split_caption fix: candidates see re-joined caption blocks, so
        # the exact full caption text wins (both passes use the same regions).
        regions = merge_split_captions(page.text_regions)
        for figure in page.figures:
            bbox_override, page_scan = _page_scan_context(figure.occurrence.bbox, page)
            results[figure.occurrence.image_id] = match_image(
                figure.occurrence,
                regions,
                page_height=page.page_height or 842.0,
                bbox_override=bbox_override,
                page_scan=page_scan,
            )

    series_passthrough(figures, results)
    return results
