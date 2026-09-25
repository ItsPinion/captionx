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

from .decision import OCRThresholds, OCR_THRESHOLDS, needs_ocr
from .engine import OCREngine, get_ocr_engine

__all__ = ["apply_ocr_when_needed"]


def apply_ocr_when_needed(
    doc: pymupdf.Document,
    page_extraction: PageExtraction,
    *,
    engine: OCREngine | None = None,
    thresholds: OCRThresholds = OCR_THRESHOLDS,
) -> bool:
    """OCR the page if its native text layer is unusable; merge regions.

    Mutates `page_extraction` in place (appends OCR regions, sets
    `ocr_used`). Returns whether OCR ran.
    """
    if not needs_ocr(page_extraction.text_regions, thresholds):
        return False

    ocr = engine if engine is not None else get_ocr_engine()
    ocr_regions = ocr.ocr_page(doc, page_extraction.page)
    page_extraction.text_regions = [*page_extraction.text_regions, *ocr_regions]
    page_extraction.ocr_used = True
    return True
