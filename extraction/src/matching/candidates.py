"""Phase 7 — caption candidate detection (plan.md §13).

For each extracted image, identify nearby text blocks on the same page that
could be its caption.

Flow (§13.1–§13.4):

    image bbox (same page only, §13.1)
      → base filters: page numbers, running headers/footers, oversized
        body blocks, figure-internal labels            (§13.3)
      → candidate windows: primary BELOW the image, secondary ABOVE
        (never the whole page, §13.2)
      → horizontal relatedness (own column only)
      → CaptionCandidate(text=bblock text, bbox, source, image_id)

Text is preserved exactly (§13.4); any normalization for scoring happens
later, inside the feature code (Phase 8).

All constants were tuned against the three fixture chapters (Class 9 NCERT
Science 1/5/12) — measured evidence in the comments:

- captions BELOW figures: gaps 4–95 pt (18 of 20 captions)
- captions ABOVE figures: gaps 138–387 pt (2 of 20)
- running footer on every page: one block at y 738–747 on the 842 pt page
  ("SCIENCE 62", "THE FUNDAMENTAL UNIT OF LIFE 59" — running head and page
  number fused); real captions/footnotes end by y ≈ 722
- no top running heads in these chapters (kept for generality)
- sub-labels like "(a)" sit between stacked figures of one experiment series
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from src.models import BBox, CaptionCandidate, ImageOccurrence, TextRegion
from src.pdf.extractor import DocumentExtraction, PageExtraction

__all__ = [
    "CANDIDATE_CONFIG",
    "CandidateConfig",
    "build_document_candidates",
    "build_page_candidates",
    "collect_candidates",
    "is_figure_internal",
    "is_oversized_block",
    "is_page_number",
    "is_running_footer",
    "is_running_header",
    "passes_base_filters",
]

#: Matches standalone page numbers: `64`, `— 64 —`, `- 64 -`, `–64–`.
_PAGE_NUMBER_RE = re.compile(r"^\s*[-–—]?\s*\d{1,4}\s*[-–—]?\s*$")


@dataclass(frozen=True)
class CandidateConfig:
    """Tuning knobs for candidate detection (one place, for Phase 32)."""

    #: Primary window: how far below the image a caption may start (§13.2).
    #: Measured true captions: 4–95 pt.
    max_below_gap_pt: float = 100.0
    #: Secondary window: how far above the image a caption may end (§13.2).
    #: A genuine above-caption was measured at 138 pt.
    max_above_gap_pt: float = 150.0
    #: A block must come this close horizontally to be related at all:
    #: either ≥ `min_horizontal_overlap_ratio` of its width overlaps the
    #: image x-range, or its x-gap to the image is ≤ this slack (catches
    #: indented short captions such as `Fig. 1.4`, measured overlap 10.6 pt).
    horizontal_slack_pt: float = 40.0
    min_horizontal_overlap_ratio: float = 0.20
    #: Running-footer band, expressed as offsets from the page bottom: a short
    #: block fully inside `[H - footer_upper_offset, H - footer_lower_offset]`
    #: is page furniture. Measured band on A4: y0 738 = 104 pt from bottom,
    #: y1 747 = 95 pt. Real captions stop ≥ 20 pt below the band's upper edge.
    footer_upper_offset_pt: float = 110.0
    footer_lower_offset_pt: float = 70.0
    footer_max_height_pt: float = 20.0
    #: Running-head band: block fully within this distance of the page top.
    header_max_y_pt: float = 50.0
    #: Body-paragraph guards (§13.3 "extremely large body-text blocks"):
    #: NCERT captions run 10–120 chars / 9–30 pt tall.
    max_block_chars: int = 600
    max_block_height_pt: float = 260.0


#: Default configuration (NCERT-tuned).
CANDIDATE_CONFIG = CandidateConfig()


# --------------------------------------------------------------------------- #
# Base filters (§13.3)


def is_page_number(text: str) -> bool:
    """True for standalone page numbers (`64`, `— 64 —`)."""
    return bool(_PAGE_NUMBER_RE.match(text))


def is_running_footer(bbox: BBox, page_height: float, cfg: CandidateConfig = CANDIDATE_CONFIG) -> bool:
    """True for short blocks fully inside the running-footer band."""
    upper = page_height - cfg.footer_upper_offset_pt
    lower = page_height - cfg.footer_lower_offset_pt
    return (
        bbox.y0 >= upper
        and bbox.y1 <= lower
        and bbox.height <= cfg.footer_max_height_pt
    )


def is_running_header(bbox: BBox, cfg: CandidateConfig = CANDIDATE_CONFIG) -> bool:
    """True for blocks fully inside the running-head band."""
    return bbox.y1 <= cfg.header_max_y_pt


def is_oversized_block(bbox: BBox, text: str, cfg: CandidateConfig = CANDIDATE_CONFIG) -> bool:
    """True for body paragraphs too large to be captions (§13.3)."""
    return len(text) > cfg.max_block_chars or bbox.height > cfg.max_block_height_pt


def passes_base_filters(
    region: TextRegion,
    page_height: float,
    cfg: CandidateConfig = CANDIDATE_CONFIG,
) -> bool:
    """Cheap, image-independent filters for §13.3 (page furniture, body text)."""
    text = region.text.strip()
    if not text:
        return False
    if is_page_number(text):
        return False
    if is_running_footer(region.bbox, page_height, cfg):
        return False
    if is_running_header(region.bbox, cfg):
        return False
    if is_oversized_block(region.bbox, text, cfg):
        return False
    return True


def is_figure_internal(region_bbox: BBox, image_bbox: BBox) -> bool:
    """True if the block's center lies inside the image bbox.

    Text drawn inside a figure (vector labels on diagram regions) belongs to
    the artwork, not to the caption.
    """
    return (
        image_bbox.x0 <= region_bbox.x_center <= image_bbox.x1
        and image_bbox.y0 <= region_bbox.y_center <= image_bbox.y1
    )


# --------------------------------------------------------------------------- #
# Candidate windows (§13.2)


def horizontally_related(
    image_bbox: BBox, region_bbox: BBox, cfg: CandidateConfig = CANDIDATE_CONFIG
) -> bool:
    """Same-column test: overlap or near-miss within slack (§13.3 columns)."""
    overlap = image_bbox.horizontal_overlap(region_bbox)
    if overlap >= cfg.min_horizontal_overlap_ratio * region_bbox.width:
        return True
    x_gap = max(image_bbox.x0 - region_bbox.x1, region_bbox.x0 - image_bbox.x1)
    return x_gap <= cfg.horizontal_slack_pt


def _vertical_relation(
    image_bbox: BBox, region_bbox: BBox, cfg: CandidateConfig
) -> Optional[str]:
    """`below` / `above` when the block is inside the respective window."""
    if region_bbox.y0 >= image_bbox.y1:
        if region_bbox.y0 - image_bbox.y1 <= cfg.max_below_gap_pt:
            return "below"
        return None
    if region_bbox.y1 <= image_bbox.y0:
        if image_bbox.y0 - region_bbox.y1 <= cfg.max_above_gap_pt:
            return "above"
    return None


def collect_candidates(
    image: ImageOccurrence,
    regions: Sequence[TextRegion],
    page_height: float,
    cfg: CandidateConfig = CANDIDATE_CONFIG,
) -> list[CaptionCandidate]:
    """All caption candidates on `image`'s page, nearest-first.

    Same-page only (§13.1); base filters + internal-label filter (§13.3);
    below/above windows (§13.2); exact text preserved (§13.4).
    """
    if image.bbox is None:
        return []

    candidates: list[CaptionCandidate] = []
    for region in regions:
        if region.page != image.page:  # §13.1 same-page restriction
            continue
        if not passes_base_filters(region, page_height, cfg):
            continue
        if is_figure_internal(region.bbox, image.bbox):
            continue
        position = _vertical_relation(image.bbox, region.bbox, cfg)
        if position is None:
            continue
        if not horizontally_related(image.bbox, region.bbox, cfg):
            continue
        candidates.append(
            CaptionCandidate(
                text=region.text,  # §13.4 exact text, untouched
                bbox=region.bbox,
                source=region.source,
                image_id=image.image_id,
            )
        )

    image_bbox = image.bbox
    image_x = image_bbox.x_center

    def sort_key(candidate: CaptionCandidate) -> tuple[float, float]:
        bbox = candidate.bbox
        distance = max(0.0, image_bbox.vertical_gap(bbox))
        x_penalty = abs(bbox.x_center - image_x)
        return (distance, x_penalty)

    candidates.sort(key=sort_key)
    return candidates


def build_page_candidates(
    page: PageExtraction,
    cfg: CandidateConfig = CANDIDATE_CONFIG,
) -> dict[str, list[CaptionCandidate]]:
    """Candidates for every figure on one page, keyed by `image_id`."""
    if page.page_height is None:
        raise ValueError("PageExtraction is missing page_height — re-extract with the current extractor")
    result: dict[str, list[CaptionCandidate]] = {}
    for figure in page.figures:
        result[figure.occurrence.image_id] = collect_candidates(
            figure.occurrence,
            page.text_regions,
            page_height=page.page_height,
            cfg=cfg,
        )
    return result


def build_document_candidates(
    document: DocumentExtraction,
    cfg: CandidateConfig = CANDIDATE_CONFIG,
) -> dict[str, list[CaptionCandidate]]:
    """Candidates for every figure in the document, keyed by `image_id`."""
    all_candidates: dict[str, list[CaptionCandidate]] = {}
    for page in document.pages:
        all_candidates.update(build_page_candidates(page, cfg))
    return all_candidates
