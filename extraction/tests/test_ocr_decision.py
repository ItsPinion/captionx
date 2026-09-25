"""Tests for the Phase 5 OCR decision (plan.md §11)."""

from src.models import BBox, TextRegion, TextSource
from src.ocr import needs_ocr
from src.ocr.decision import OCR_THRESHOLDS


def regions_with_total_chars(total: int) -> list[TextRegion]:
    regions = []
    remaining = total
    while remaining > 0:
        chunk = "x" * min(remaining, 50)
        regions.append(
            TextRegion(
                text=chunk,
                bbox=BBox(0, 0, 10, 10),
                source=TextSource.NATIVE_PDF,
                page=1,
            )
        )
        remaining -= len(chunk)
    return regions


class TestNeedsOcr:
    def test_no_native_text_needs_ocr(self):
        """Scanned/image-only page."""
        assert needs_ocr([]) is True

    def test_scarce_native_text_needs_ocr(self):
        assert needs_ocr(regions_with_total_chars(10)) is True

    def test_boundary_at_threshold(self):
        limit = OCR_THRESHOLDS.min_usable_native_chars
        assert needs_ocr(regions_with_total_chars(limit - 1)) is True
        assert needs_ocr(regions_with_total_chars(limit)) is False

    def test_rich_native_text_does_not_need_ocr(self):
        """The target NCERT pages carry thousands of native chars."""
        assert needs_ocr(regions_with_total_chars(2000)) is False

    def test_custom_thresholds(self):
        from src.ocr.decision import OCRThresholds

        strict = OCRThresholds(min_usable_native_chars=500)
        assert needs_ocr(regions_with_total_chars(200), strict) is True
