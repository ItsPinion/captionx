"""Native PDF text extraction (plan.md §10.4).

Uses `page.get_text("blocks")` and preserves each block's text exactly
(no normalization — plan.md §13.4) together with its bbox, so the caption
matcher can reason spatially. Blocks are returned in the PDF's own block
order, which for NCERT chapters follows the reading flow well enough for
candidate detection.

Fused-caption split (unseen-PDF generalization): some editions glue a
caption head into a block that does not *start* with it — e.g. the running
footer fused above the caption ("MATTER AROUND US PURE ⏎ Fig. 2.5:
Evaporation", Class 9 ch02 p6 — the fused block even lands inside the
footer band and was dropped wholesale), or a stray body line above it
("by sublimation ⏎ Fig. 2.6: …", ch02 p7 — the head prefix feature then
scored zero). When a block contains a `Fig.`-head line after its first
line, the block is split at that line's measured y into a junk region and
a clean caption-head region; both keep their exact sub-texts (§13.4).
Blocks that already start with the caption (all pinned fixtures) are
untouched — zero behavioral change there.
"""

from __future__ import annotations

from typing import Optional

import re

import pymupdf

from src.models import BBox, TextRegion, TextSource

__all__ = ["extract_text_regions"]

#: Same caption-head pattern as matching/candidates.py (§13): kept local to
#: avoid a pdf → matching import cycle. Matches `Fig. 1.2: …`, `Fig2.3: …`.
_CAPTION_HEAD_LINE_RE = re.compile(r"^\s*Fig\.?\s*\d", re.I)


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
        clean = text.rstrip("\n")
        bbox = BBox(float(x0), float(y0), float(x1), float(y1))
        split = _split_fused_caption_block(page, clean, bbox)
        if split is None:
            regions.append(
                TextRegion(text=clean, bbox=bbox, source=TextSource.NATIVE_PDF, page=page_no)
            )
            continue
        pre_text, pre_bbox, head_text, head_bbox = split
        regions.append(
            TextRegion(text=pre_text, bbox=pre_bbox, source=TextSource.NATIVE_PDF, page=page_no)
        )
        regions.append(
            TextRegion(text=head_text, bbox=head_bbox, source=TextSource.NATIVE_PDF, page=page_no)
        )
    return regions


def _head_split_y(page: pymupdf.Page, head_line: str, bbox: BBox) -> float | None:
    """Measured y0 of the line `head_line` inside the block at `bbox`.

    The dict pass runs only for the rare fused blocks, and the line is
    matched by its (whitespace-normalized) text — block text and dict lines
    describe the same glyphs, but index alignment between the two extraction
    modes is not guaranteed. `None` when the line cannot be located.
    """
    want = " ".join(head_line.split())
    for dblock in page.get_text("dict", clip=(bbox.x0, bbox.y0, bbox.x1, bbox.y1))["blocks"]:
        if dblock.get("type") != 0:
            continue
        for line in dblock["lines"]:
            line_text = "".join(span["text"] for span in line["spans"])
            if " ".join(line_text.split()) == want:
                y = line["bbox"][1]
                # The head line may sit exactly at the block top: in ch02 p7
                # the bold caption starts 1.8 pt ABOVE the stray line that
                # precedes it in reading order, so its y0 equals the block's.
                # (y == bbox.y1 is still rejected — that would zero the head.)
                if bbox.y0 <= y < bbox.y1:
                    return y
    return None


def _split_fused_caption_block(
    page: pymupdf.Page, text: str, bbox: BBox
) -> Optional[tuple[str, BBox, str, BBox]]:
    """Split a block with an embedded `Fig.` head line into junk + caption.

    Returns `(pre_text, pre_bbox, head_text, head_bbox)` or `None` when the
    block does not carry a caption head after its first line (the common
    case — no dict pass, no change). Sub-texts are the block's own lines,
    unchanged (§13.4); the bboxes split the block at the head line's
    measured y.
    """
    lines = text.split("\n")
    head_idx = next((i for i in range(1, len(lines)) if _CAPTION_HEAD_LINE_RE.match(lines[i])), None)
    if head_idx is None:
        return None
    split_y = _head_split_y(page, lines[head_idx], bbox)
    if split_y is None:
        return None
    pre_text = "\n".join(lines[:head_idx])
    head_text = "\n".join(lines[head_idx:])
    pre_bbox = BBox(bbox.x0, bbox.y0, bbox.x1, split_y)  # may be zero-height
    head_bbox = BBox(bbox.x0, split_y, bbox.x1, bbox.y1)
    return pre_text, pre_bbox, head_text, head_bbox
