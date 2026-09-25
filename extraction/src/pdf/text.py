"""Native PDF text extraction (plan.md §10.4).

Uses `page.get_text("blocks")` and preserves each block's text exactly
(no normalization — plan.md §13.4) together with its bbox, so the caption
matcher can reason spatially. Blocks are returned in the PDF's own block
order, which for NCERT chapters follows the reading flow well enough for
candidate detection.
"""

from __future__ import annotations

import pymupdf

from src.models import BBox, TextRegion, TextSource

__all__ = ["extract_text_regions"]


def extract_text_regions(page: pymupdf.Page) -> list[TextRegion]:
    """All native text blocks on `page` as `TextRegion`s (type-0 blocks only).

    Image blocks (`type == 1`) are handled by `images.py`; empty/whitespace
    blocks are skipped. Text is preserved exactly except for a trailing
    newline strip that `get_text` appends to the final block.
    """
    page_no = page.number + 1  # PyMuPDF is 0-based; the model is 1-based
    regions: list[TextRegion] = []
    for block in page.get_text("blocks"):
        x0, y0, x1, y1, text, _block_no, block_type = block
        if block_type != 0:  # 1 = image block
            continue
        if not text.strip():
            continue
        regions.append(
            TextRegion(
                text=text.rstrip("\n"),
                bbox=BBox(float(x0), float(y0), float(x1), float(y1)),
                source=TextSource.NATIVE_PDF,
                page=page_no,
            )
        )
    return regions
