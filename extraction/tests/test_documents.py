"""Tests for Document, ImageOccurrence and TextRegion (plan.md §9)."""

import pytest

from src.models import (
    BBox,
    Document,
    DocumentSource,
    ImageOccurrence,
    TextRegion,
    TextSource,
    make_image_filename,
    make_image_id,
)


class TestDocument:
    def test_construction_and_defaults(self):
        doc = Document(
            document_id="job_001",
            filename="biology_ch01.pdf",
            page_count=18,
            source=DocumentSource.UPLOAD,
        )
        assert doc.source is DocumentSource.UPLOAD

    def test_source_coerced_from_string(self):
        doc = Document(
            document_id="j", filename="f.pdf", page_count=3, source="url"
        )
        assert doc.source is DocumentSource.URL

    def test_invalid_page_count_rejected(self):
        with pytest.raises(ValueError):
            Document(document_id="j", filename="f.pdf", page_count=0, source="upload")

    def test_invalid_source_rejected(self):
        with pytest.raises(ValueError):
            Document(document_id="j", filename="f.pdf", page_count=2, source="scp")

    def test_to_dict_matches_results_json_metadata(self):
        """plan.md §13: document metadata is filename/source/page_count."""
        doc = Document(
            document_id="job_001",
            filename="biology_ch01.pdf",
            page_count=18,
            source=DocumentSource.UPLOAD,
        )
        assert doc.to_dict() == {
            "filename": "biology_ch01.pdf",
            "source": "upload",
            "page_count": 18,
        }

    def test_roundtrip(self):
        doc = Document(
            document_id="job_001", filename="f.pdf", page_count=9, source="url"
        )
        assert Document.from_dict({**doc.to_dict(), "document_id": doc.document_id}) == doc


class TestImageOccurrence:
    def test_image_id_derived_from_page_and_index(self):
        img = ImageOccurrence(
            page=3, index=2, width=640, height=480, filename="x.png"
        )
        assert img.image_id == make_image_id(3, 2)
        assert img.image_id == "page_03_image_02"

    def test_explicit_image_id_preserved(self):
        img = ImageOccurrence(
            page=1, index=1, width=10, height=10, filename="a.png",
            image_id="custom-id",
        )
        assert img.image_id == "custom-id"

    def test_filename_convention(self):
        """plan.md §10.3: <document>_page_<page>_image_<index>.png."""
        assert make_image_filename("biology_ch01", 3, 1) == (
            "biology_ch01_page_03_image_01.png"
        )

    def test_page_and_index_one_based(self):
        with pytest.raises(ValueError):
            ImageOccurrence(page=0, index=1, width=1, height=1, filename="a.png")
        with pytest.raises(ValueError):
            ImageOccurrence(page=1, index=0, width=1, height=1, filename="a.png")

    def test_bbox_optional(self):
        """Xrefs without placement must not break the model."""
        img = ImageOccurrence(page=4, index=1, width=8, height=8, filename="b.png")
        assert img.bbox is None

    def test_roundtrip_with_bbox(self):
        img = ImageOccurrence(
            page=4,
            index=3,
            width=640,
            height=480,
            filename="b.png",
            bbox=BBox(10, 20, 300, 200),
        )
        assert ImageOccurrence.from_dict(img.to_dict()) == img

    def test_no_deduplication_two_occurrences_distinct(self):
        """plan.md §12: same image twice → two separate records."""
        a = ImageOccurrence(page=4, index=1, width=8, height=8, filename="a.png")
        b = ImageOccurrence(page=9, index=1, width=8, height=8, filename="b.png")
        assert a.image_id != b.image_id


class TestTextRegion:
    def test_native_region(self):
        r = TextRegion(
            text="Fig. 3.1: Structure of the cell",
            bbox=BBox(100, 410, 300, 430),
            source=TextSource.NATIVE_PDF,
            page=3,
        )
        assert r.source is TextSource.NATIVE_PDF

    def test_ocr_region(self):
        r = TextRegion(
            text="Fig. 3.1: Structure of the cell",
            bbox=BBox(100, 410, 300, 430),
            source="ocr",
            page=3,
        )
        assert r.source is TextSource.OCR

    def test_source_serializes_to_contract_strings(self):
        r = TextRegion(
            text="t", bbox=BBox(0, 0, 1, 1), source=TextSource.NATIVE_PDF, page=1
        )
        assert r.to_dict()["source"] == "native_pdf"

    def test_roundtrip(self):
        r = TextRegion(
            text="hello world",
            bbox=BBox(5, 6, 7, 8),
            source=TextSource.OCR,
            page=12,
        )
        assert TextRegion.from_dict(r.to_dict()) == r
