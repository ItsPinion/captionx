"""Phase 5 — decide when OCR is needed (plan.md §11).

Decision flow:

    PDF page → native text extraction → usable text?
        ├─ yes → use native text
        └─ no / suspicious → render page → PaddleOCR

The plan says: "Do not over-engineer this detector. Start with a simple rule."
The target NCERT chapters all carry a rich native text layer, so the only
real failure signal is a page with (almost) no native text — a scanned or
image-only page, or a broken text layer.

`OCR_THRESHOLDS.suspicious_page_signals` documents the signals we considered;
only the first is implemented for now.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from src.models import TextRegion

__all__ = ["OCR_THRESHOLDS", "OCRThresholds", "native_char_count", "needs_ocr"]


@dataclass(frozen=True)
class OCRThresholds:
    """Tunable knobs for the OCR decision (kept in one place for Phase 32 tuning)."""

    #: Pages whose total native text is below this are considered unusable.
    min_usable_native_chars: int = 32


OCR_THRESHOLDS = OCRThresholds()

# Suspicious-page signals from plan.md §11; implemented: (1).
# 1. almost no native text but the page visibly contains content  → implemented
# 2. text blocks missing where an apparent caption should exist   → later, only
#    if NCERT chapters prove it necessary (would couple detection to figures)
# 3. page appears image-heavy                                     → not a text-
#    failure signal on its own; NCERT figure pages have plenty of native text
# 4. extracted text is obviously incomplete                       → same rule as 1


def native_char_count(regions: Sequence[TextRegion]) -> int:
    return sum(len(region.text) for region in regions)


def needs_ocr(
    native_regions: Sequence[TextRegion],
    thresholds: OCRThresholds = OCR_THRESHOLDS,
) -> bool:
    """True when the page's native text layer is not usable."""
    return native_char_count(native_regions) < thresholds.min_usable_native_chars
