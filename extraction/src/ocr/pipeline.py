"""Phase 6 — OCR woven into the page pipeline (plan.md §11 output / §12).

Implements the §11 output contract:

    Each page ultimately has text_regions[] with each region tagged
    `native_pdf` or `ocr`.

`apply_ocr_when_needed` is the single integration point used by the job
pipeline (Phase 15's `main.py`): for a page whose native text is unusable it
runs the OCR engine and merges the OCR regions into `PageExtraction`, keeping
the native regions (a partially-broken text layer still carries useful
blocks). The page records that OCR ran so the matching stage can label
results `method="ocr"` later (plan.md §13).
"""

from __future__ import annotations

import pymupdf

from src.pdf.extractor import PageExtraction

from src.models import BBox, LayoutRegion

from .decision import OCRThresholds, OCR_THRESHOLDS, needs_ocr
from .engine import OCREngine, get_ocr_engine

__all__ = ["apply_ocr_when_needed", "caption_crop_rect"]

#: Padding (points) around a caption region for the clipped OCR render.
_CROP_PAD_PT = 6.0


def caption_crop_rect(region: LayoutRegion, page_bbox: BBox | None) -> BBox | None:
    """Padded, page-clamped crop box for one caption region (or None)."""
    x0 = max(0.0, region.bbox.x0 - _CROP_PAD_PT)
    y0 = max(0.0, region.bbox.y0 - _CROP_PAD_PT)
    x1 = region.bbox.x1 + _CROP_PAD_PT
    y1 = region.bbox.y1 + _CROP_PAD_PT
    if page_bbox is not None:
        x1 = min(x1, page_bbox.x1)
        y1 = min(y1, page_bbox.y1)
    if x1 <= x0 or y1 <= y0:
        return None
    return BBox(x0, y0, x1, y1)


def apply_ocr_when_needed(
    doc: pymupdf.Document,
    page_extraction: PageExtraction,
    *,
    engine: OCREngine | None = None,
    thresholds: OCRThresholds = OCR_THRESHOLDS,
    caption_regions: list[LayoutRegion] | None = None,
) -> bool:
    """OCR the page if its native text layer is unusable; merge regions.

    Final plan §12: when PP-DocLayout-S found `figure_title` regions, OCR
    reads those crops (targeted, cheaper, layout-tagged) and falls back to
    a whole-page pass only when no caption region yields text.

    Mutates `page_extraction` in place (appends OCR regions, sets
    `ocr_used`). Returns whether OCR ran.
    """
    if not needs_ocr(page_extraction.text_regions, thresholds):
        return False

    ocr = engine if engine is not None else get_ocr_engine()
    ocr_regions: list = []
    if caption_regions:
        page_bbox = (
            BBox(0.0, 0.0, page_extraction.page_width or 0.0, page_extraction.page_height or 0.0)
            if page_extraction.page_width
            else None
        )
        for region in caption_regions:
            crop = caption_crop_rect(region, page_bbox)
            if crop is None:
                continue
            ocr_regions.extend(
                ocr.ocr_page(
                    doc,
                    page_extraction.page,
                    clip=(crop.x0, crop.y0, crop.x1, crop.y1),
                    layout_label=region.label,
                    layout_confidence=region.confidence,
                )
            )
    if not ocr_regions:
        # No caption regions (or they OCR'd empty) → whole-page fallback.
        ocr_regions = list(ocr.ocr_page(doc, page_extraction.page))
    page_extraction.text_regions = [*page_extraction.text_regions, *ocr_regions]
    page_extraction.ocr_used = True
    return True
