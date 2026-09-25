"""Tests for the Phase 6 page-pipeline OCR integration (§11 output / §12)."""

from unittest.mock import MagicMock

import pymupdf

from src.models import BBox, TextRegion, TextSource
from src.ocr import apply_ocr_when_needed
from src.ocr.decision import OCRThresholds
from src.pdf.extractor import PageExtraction
from tests.pdf_fixtures import add_text, new_page


def native_region(text: str, page: int = 1) -> TextRegion:
    return TextRegion(
        text=text,
        bbox=BBox(70, 100, 300, 120),
        source=TextSource.NATIVE_PDF,
        page=page,
    )


def ocr_region(text: str, page: int = 1) -> TextRegion:
    return TextRegion(
        text=text,
        bbox=BBox(70, 400, 300, 420),
        source=TextSource.OCR,
        page=page,
    )


def fake_engine(regions: list[TextRegion]) -> MagicMock:
    engine = MagicMock()
    engine.ocr_page.return_value = regions
    return engine


def open_doc_with_page() -> pymupdf.Document:
    doc, page = new_page()
    add_text(page, "placeholder so the page exists", (72, 72))
    return doc


class TestApplyOcrWhenNeeded:
    def test_rich_native_text_skips_ocr(self):
        """§11: usable native text → OCR must not run (cheap path)."""
        doc = open_doc_with_page()
        page_extraction = PageExtraction(
            page=1, text_regions=[native_region("x" * 200)]
        )
        engine = fake_engine([ocr_region("should not appear")])

        ran = apply_ocr_when_needed(doc, page_extraction, engine=engine)

        assert ran is False
        engine.ocr_page.assert_not_called()
        assert page_extraction.ocr_used is False
        assert len(page_extraction.text_regions) == 1

    def test_empty_native_text_triggers_ocr_and_merges(self):
        """Scanned page: OCR regions appended, page flagged."""
        doc = open_doc_with_page()
        page_extraction = PageExtraction(page=1, text_regions=[])
        engine = fake_engine(
            [ocr_region("Fig. 3.1"), ocr_region("Structure of the cell")]
        )

        ran = apply_ocr_when_needed(doc, page_extraction, engine=engine)

        assert ran is True
        engine.ocr_page.assert_called_once()
        sources = {r.source for r in page_extraction.text_regions}
        assert sources == {TextSource.OCR}
        assert page_extraction.ocr_used is True
        assert len(page_extraction.text_regions) == 2

    def test_scarce_native_text_keeps_native_and_adds_ocr(self):
        """Partially broken text layer: native blocks kept, OCR appended."""
        doc = open_doc_with_page()
        page_extraction = PageExtraction(
            page=1, text_regions=[native_region("tiny")]
        )  # 4 chars < threshold
        engine = fake_engine([ocr_region("recovered caption text")])

        ran = apply_ocr_when_needed(doc, page_extraction, engine=engine)

        assert ran is True
        texts = [r.text for r in page_extraction.text_regions]
        assert texts == ["tiny", "recovered caption text"]
        assert page_extraction.ocr_used is True

    def test_custom_thresholds_respected(self):
        doc = open_doc_with_page()
        page_extraction = PageExtraction(
            page=1, text_regions=[native_region("x" * 200)]
        )
        strict = OCRThresholds(min_usable_native_chars=500)
        engine = fake_engine([ocr_region("ocr")])

        ran = apply_ocr_when_needed(doc, page_extraction, engine=engine, thresholds=strict)

        assert ran is True
        assert page_extraction.ocr_used is True

    def test_ocr_page_number_passed_through(self):
        doc = open_doc_with_page()
        doc.new_page()
        page_extraction = PageExtraction(page=2, text_regions=[])
        engine = fake_engine([ocr_region("p2 text", page=2)])

        apply_ocr_when_needed(doc, page_extraction, engine=engine)

        engine.ocr_page.assert_called_once()
        assert engine.ocr_page.call_args[0][1] == 2
        assert all(r.page == 2 for r in page_extraction.text_regions)
