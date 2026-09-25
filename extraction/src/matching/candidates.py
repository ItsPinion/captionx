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

from src.models import BBox, CaptionCandidate, ImageOccurrence, LayoutRegion, TextRegion
from src.ocr.layout import CAPTION_LABELS, IMAGE_LABELS
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
    "tag_layout_barriers",
]

#: Matches standalone page numbers: `64`, `— 64 —`, `- 64 -`, `–64–`.
_PAGE_NUMBER_RE = re.compile(r"^\s*[-–—]?\s*\d{1,4}\s*[-–—]?\s*$")

#: A caption head: `Fig. 1.2: …`, `Fig 12.12: …`, `Fig.12.13: …`.
_CAPTION_HEAD_RE = re.compile(r"^\s*Fig\.?\s*\d", re.I)

#: Blocks that must never be absorbed as caption continuations: the head of
#: the *next* caption, or the start of a bulleted list.
_NOT_CONTINUATION_RE = re.compile(r"^\s*(Fig\.?\s*\d|•)", re.I)


@dataclass(frozen=True)
class CandidateConfig:
    """Tuning knobs for candidate detection (one place, for Phase 32)."""

    #: Primary window: how far below the image a caption may start (§13.2).
    #: Measured true captions: 4–95 pt.
    max_below_gap_pt: float = 100.0
    #: Secondary window: how far above the image a caption may sit (§13.2).
    #: Kept small: the measured far "above-caption" (138 pt, ch12 p5) turned
    #: out to be a biography portrait mispaired in Phase 11 — §33 inspection
    #: showed no true above-caption beyond ~60 pt in these chapters.
    max_above_gap_pt: float = 60.0
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
    #: §38 split_caption fix: a caption head re-joins a following block when
    #: the continuation starts within this gap. Measured true continuations:
    #: 1.8–3.0 pt (Figs 1.2, 1.5, 1.6, 12.6, 12.8).
    continuation_max_gap_pt: float = 3.5
    #: …and when the block x-ranges overlap (± this slack). The measured trap:
    #: body text in the *neighbouring column* sits 2.8 pt below a caption but
    #: never overlaps it horizontally (Fig 5.5 vs "We have talked about…").
    continuation_x_slack_pt: float = 2.0
    #: Safety cap on absorbed continuation blocks per caption head.
    max_continuation_blocks: int = 2
    #: Final plan §11 (DL-driven matching): a PP-DocLayout-S figure_title-
    #: tagged block is admitted even beyond the strict windows — DL authority
    #: — but never farther than this multiple of the window (a "caption" half
    #: a page away is a misread region, not evidence).
    layout_admit_gap_factor: float = 1.5
    #: …and must share the figure's column: ≥ this fraction of the tagged
    #: block's width overlaps the image x-range (else the x-gap slack applies).
    layout_admit_min_overlap: float = 0.25
    #: A layout `figure` region starting this far below the image acts as a
    #: barrier: a below-candidate at/beyond its top edge belongs to the NEXT
    #: figure (soft flag — the matcher prefers unbarriered near-ties).
    barrier_min_figure_gap_pt: float = 4.0


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


def _layout_admission(
    effective_bbox: BBox, region: TextRegion, cfg: CandidateConfig
) -> Optional[str]:
    """DL admission (final plan §11): `below`/`above` beyond the windows.

    PP-DocLayout-S labeled this block a caption region. The model — not the
    tuned gap — decides it belongs to this figure, subject to sanity bounds:
    within 1.5× the strict window and sharing the figure's column. Returns
    the position label, or None when the DL claim is out of bounds.
    """
    if region.bbox.y0 >= effective_bbox.y1:
        position = "below"
        gap = region.bbox.y0 - effective_bbox.y1
    elif region.bbox.y1 <= effective_bbox.y0:
        position = "above"
        gap = effective_bbox.y0 - region.bbox.y1
    else:
        return None  # intersecting the image: neither window applies
    limit = (
        cfg.max_below_gap_pt if position == "below" else cfg.max_above_gap_pt
    ) * cfg.layout_admit_gap_factor
    if gap > limit:
        return None
    overlap = effective_bbox.horizontal_overlap(region.bbox)
    if overlap < cfg.layout_admit_min_overlap * region.bbox.width:
        x_gap = max(effective_bbox.x0 - region.bbox.x1, region.bbox.x0 - effective_bbox.x1)
        if x_gap > cfg.horizontal_slack_pt:
            return None
    return position


def _beyond_layout_barrier(
    effective_bbox: BBox,
    candidate_bbox: BBox,
    layout_regions: Sequence[LayoutRegion],
    cfg: CandidateConfig,
) -> bool:
    """True when a DL `figure` region for ANOTHER figure intervenes.

    A below-candidate starting at/beyond the top edge of the next figure
    region (same column, region strictly below our image) most likely
    captions that next figure — the DL-drawn figure boundary bounds our
    candidate window (soft: the matcher only prefers unbarriered near-ties).
    """
    for lr in layout_regions:
        if lr.label not in IMAGE_LABELS:
            continue
        fig = lr.bbox
        if fig.y0 < effective_bbox.y1 + cfg.barrier_min_figure_gap_pt:
            continue  # not a separate figure below ours
        if fig.horizontal_overlap(candidate_bbox) < 0.3 * candidate_bbox.width:
            continue  # different column than the candidate
        if candidate_bbox.y0 >= fig.y0 - 1.0:
            return True
    return False


def collect_candidates(
    image: ImageOccurrence,
    regions: Sequence[TextRegion],
    page_height: float,
    cfg: CandidateConfig = CANDIDATE_CONFIG,
    *,
    bbox_override: BBox | None = None,
    page_scan: bool = False,
    layout_regions: Sequence[LayoutRegion] = (),
) -> list[CaptionCandidate]:
    """All caption candidates on `image`'s page, nearest-first.

    Same-page only (§13.1); base filters + internal-label filter (§13.3);
    below/above windows (§13.2); exact text preserved (§13.4).

    Final plan §11: for a scanned page (one raster covering most of it)
    PP-DocLayout-S's figure region is the effective image bbox
    (`bbox_override`) and the figure-internal filter is disabled — every
    real text block of a scan sits "inside" the page raster.

    DL authority (final plan §11): a figure_title-tagged block bypasses the
    window/column checks within sanity bounds (`_layout_admission`) — the
    layout model, not the tuned gap, decides that nearby caption-shaped text
    belongs to this figure.
    """
    effective_bbox = bbox_override if bbox_override is not None else image.bbox
    if effective_bbox is None:
        return []

    candidates: list[CaptionCandidate] = []
    for region in regions:
        if region.page != image.page:  # §13.1 same-page restriction
            continue
        if not passes_base_filters(region, page_height, cfg):
            continue
        layout_tagged = region.layout_label in CAPTION_LABELS
        if not page_scan and not layout_tagged and is_figure_internal(region.bbox, effective_bbox):
            continue
        position = _vertical_relation(effective_bbox, region.bbox, cfg)
        if position is not None:
            # In-window: the strict column rule decides ownership for everyone
            # — the DL tag confirms caption-ness, geometry decides ownership.
            if not horizontally_related(effective_bbox, region.bbox, cfg):
                continue
        elif layout_tagged:
            # Out-of-window: DL admission — the model vouches that this
            # caption region belongs to this figure, within sanity bounds.
            position = _layout_admission(effective_bbox, region, cfg)
            if position is None:
                continue
        else:
            continue
        candidates.append(
            CaptionCandidate(
                text=region.text,  # §13.4 exact text, untouched
                bbox=region.bbox,
                source=region.source,
                image_id=image.image_id,
                layout_label=region.layout_label,
            )
        )

    image_bbox = effective_bbox
    image_x = image_bbox.x_center

    def sort_key(candidate: CaptionCandidate) -> tuple[float, float]:
        bbox = candidate.bbox
        distance = max(0.0, image_bbox.vertical_gap(bbox))
        x_penalty = abs(bbox.x_center - image_x)
        return (distance, x_penalty)

    candidates.sort(key=sort_key)
    return candidates


def merge_split_captions(
    regions: Sequence[TextRegion],
    cfg: CandidateConfig = CANDIDATE_CONFIG,
) -> list[TextRegion]:
    """Re-join captions the PDF splitter broke into consecutive blocks (§38).

    NCERT measurement: five true captions (Figs 1.2, 1.5, 1.6, 12.6, 12.8)
    continue in a second block sitting 1.8–3.0 pt below the head, horizontally
    overlapping it (same column). Body text in the neighbouring column can be
    almost as close (2.8 pt) but never overlaps horizontally — so BOTH a tight
    gap and an x-range overlap are required. Exact block texts are preserved
    and joined with a single space (§13.4); the bbox is the union.
    """
    order = sorted(range(len(regions)), key=lambda i: (regions[i].bbox.y0, regions[i].bbox.x0))
    used: set[int] = set()
    merged: list[TextRegion] = []

    for pos, i in enumerate(order):
        if i in used:
            continue
        head = regions[i]
        text = head.text
        x0, y0, x1, y1 = head.bbox.x0, head.bbox.y0, head.bbox.x1, head.bbox.y1
        if _CAPTION_HEAD_RE.match(head.text):
            for _ in range(cfg.max_continuation_blocks):
                found: int | None = None
                for j in order[pos + 1 :]:
                    if j in used:
                        continue
                    other = regions[j]
                    gap = other.bbox.y0 - y1
                    if not (0.0 < gap <= cfg.continuation_max_gap_pt):
                        continue
                    overlap = (
                        other.bbox.x0 < x1 + cfg.continuation_x_slack_pt
                        and x0 < other.bbox.x1 + cfg.continuation_x_slack_pt
                    )
                    if not overlap:
                        continue
                    if _NOT_CONTINUATION_RE.match(other.text):
                        continue
                    found = j
                    break
                if found is None:
                    break
                used.add(found)
                cont = regions[found]
                text = f"{text} {cont.text}"
                x0, y0 = min(x0, cont.bbox.x0), min(y0, cont.bbox.y0)
                x1, y1 = max(x1, cont.bbox.x1), max(y1, cont.bbox.y1)
        merged.append(
            TextRegion(
                text=text,
                bbox=BBox(x0=x0, y0=y0, x1=x1, y1=y1),
                source=head.source,
                page=head.page,
                # DL evidence survives the §38 merge: the head block carries
                # the PP-DocLayout-S figure_title tag (final plan §11).
                layout_label=head.layout_label,
                layout_confidence=head.layout_confidence,
            )
        )
    return merged


def tag_layout_barriers(
    image_bbox: BBox,
    candidates: Sequence[CaptionCandidate],
    layout_regions: Sequence[LayoutRegion],
    cfg: CandidateConfig = CANDIDATE_CONFIG,
) -> None:
    """Flag below-candidates that start at/beyond the NEXT figure's region.

    Mutates `candidate.features` in place (call after feature annotation).
    The flag is soft authority: the matcher prefers an unbarriered candidate
    when scores are close, but never overrides a clear winner.
    """
    for candidate in candidates:
        if candidate.bbox.y0 < image_bbox.y1:
            continue  # above/intersecting candidates have no barrier notion
        if _beyond_layout_barrier(image_bbox, candidate.bbox, layout_regions, cfg):
            if candidate.features is None:
                candidate.features = {}
            candidate.features["beyond_layout_barrier"] = 1.0


def build_page_candidates(
    page: PageExtraction,
    cfg: CandidateConfig = CANDIDATE_CONFIG,
) -> dict[str, list[CaptionCandidate]]:
    """Candidates for every figure on one page, keyed by `image_id`."""
    if page.page_height is None:
        raise ValueError("PageExtraction is missing page_height — re-extract with the current extractor")
    regions = merge_split_captions(page.text_regions, cfg)
    result: dict[str, list[CaptionCandidate]] = {}
    for figure in page.figures:
        result[figure.occurrence.image_id] = collect_candidates(
            figure.occurrence,
            regions,
            page_height=page.page_height,
            cfg=cfg,
            layout_regions=page.layout_regions,
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
