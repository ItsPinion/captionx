"""Tests for Phase 13/14 — results.json and results.csv writers."""

import csv
import json

from src.models import (
    BBox,
    Document,
    DocumentSource,
    ImageOccurrence,
    MatchMethod,
    MatchResult,
    MatchStatus,
)
from src.output import build_results_payload, write_results_csv, write_results_json
from src.pdf.extractor import DocumentExtraction, ExtractedFigure, PageExtraction
from src.pdf.images import FigureKind


def make_extraction() -> DocumentExtraction:
    doc = Document(
        document_id="job_001",
        filename="biology_ch01.pdf",
        page_count=2,
        source=DocumentSource.UPLOAD,
    )
    img1 = ImageOccurrence(
        page=1, index=1, width=640, height=480,
        filename="biology_ch01_page_01_image_01.png",
        bbox=BBox(100, 100, 300, 300),
    )
    img2 = ImageOccurrence(
        page=2, index=1, width=100, height=100,
        filename="biology_ch01_page_02_image_01.png",
        bbox=BBox(50, 400, 150, 500),
    )
    return DocumentExtraction(
        document=doc,
        pages=[
            PageExtraction(
                page=1,
                figures=[ExtractedFigure(occurrence=img1, png=b"", kind=FigureKind.STANDALONE)],
                text_regions=[],
                page_width=595.0,
                page_height=842.0,
            ),
            PageExtraction(
                page=2,
                figures=[ExtractedFigure(occurrence=img2, png=b"", kind=FigureKind.COMPOSITE)],
                text_regions=[],
                page_width=595.0,
                page_height=842.0,
            ),
        ],
    )


def make_results() -> dict[str, MatchResult]:
    return {
        "page_01_image_01": MatchResult(
            image_id="page_01_image_01",
            caption="Fig. 3.1: Structure of the cell",
            confidence=0.94,
            status=MatchStatus.MATCHED,
            method=MatchMethod.NATIVE_TEXT,
        ),
        "page_02_image_01": MatchResult(
            image_id="page_02_image_01",
            caption=None,
            confidence=0.18,
            status=MatchStatus.CAPTION_NOT_FOUND,
            method=MatchMethod.NO_RELIABLE_CANDIDATE,
        ),
    }


class TestJsonWriter:
    def test_payload_matches_plan_schema(self):
        """plan.md §19 example structure, field for field."""
        payload = build_results_payload(make_extraction(), make_results())
        assert payload["document"] == {
            "filename": "biology_ch01.pdf",
            "source": "upload",
            "page_count": 2,
        }
        assert len(payload["images"]) == 2
        assert payload["images"][0] == {
            "image": "biology_ch01_page_01_image_01.png",
            "page": 1,
            "caption": "Fig. 3.1: Structure of the cell",
            "confidence": 0.94,
            "status": "matched",
            "method": "native_text",
        }

    def test_caption_not_found_shape(self):
        """plan.md §19: null caption, honest status/method."""
        payload = build_results_payload(make_extraction(), make_results())
        entry = payload["images"][1]
        assert entry["caption"] is None
        assert entry["status"] == "caption_not_found"
        assert entry["method"] == "no_reliable_candidate"

    def test_write_and_reload(self, tmp_path):
        target = tmp_path / "results.json"
        written = write_results_json(target, make_extraction(), make_results())
        loaded = json.loads(target.read_text(encoding="utf-8"))
        assert loaded == written

    def test_unicode_captions_not_escaped(self, tmp_path):
        extraction = make_extraction()
        results = {
            "page_01_image_01": MatchResult(
                image_id="page_01_image_01",
                caption="Fig. 5.6: Zellkern — Zellkern",
                confidence=0.9,
                status=MatchStatus.MATCHED,
                method=MatchMethod.OCR,
            ),
            "page_02_image_01": MatchResult(
                image_id="page_02_image_01", caption=None, confidence=0.0,
                status=MatchStatus.CAPTION_NOT_FOUND,
                method=MatchMethod.NO_RELIABLE_CANDIDATE,
            ),
        }
        target = tmp_path / "results.json"
        write_results_json(target, extraction, results)
        raw = target.read_text(encoding="utf-8")
        assert "Zellkern — Zellkern" in raw  # not \u2014 escaped

    def test_missing_result_falls_back_to_not_found(self):
        """Defensive: a figure without a MatchResult must not crash output."""
        payload = build_results_payload(make_extraction(), {})
        assert payload["images"][0]["status"] == "caption_not_found"


class TestCsvWriter:
    def test_columns_and_rows(self, tmp_path):
        target = tmp_path / "results.csv"
        rows = write_results_csv(target, make_extraction(), make_results())
        assert rows == 2
        lines = target.read_text(encoding="utf-8").splitlines()
        assert lines[0] == "image,page,caption,confidence,status,method"
        assert len(lines) == 3

    def test_quoting_of_commas_and_quotes(self, tmp_path):
        """plan.md §20: caption fields quoted correctly, text preserved."""
        extraction = make_extraction()
        tricky = 'Fig. 1.2: "Estimating", small particles'
        results = {
            "page_01_image_01": MatchResult(
                image_id="page_01_image_01", caption=tricky,
                confidence=0.8, status=MatchStatus.MATCHED,
                method=MatchMethod.NATIVE_TEXT,
            ),
            "page_02_image_01": MatchResult(
                image_id="page_02_image_01", caption=None, confidence=0.0,
                status=MatchStatus.CAPTION_NOT_FOUND,
                method=MatchMethod.NO_RELIABLE_CANDIDATE,
            ),
        }
        target = tmp_path / "results.csv"
        write_results_csv(target, extraction, results)
        with open(target, encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
        assert rows[1][2] == tricky  # exact text survived quoting

    def test_multiline_caption_stays_one_row(self, tmp_path):
        extraction = make_extraction()
        results = {
            "page_01_image_01": MatchResult(
                image_id="page_01_image_01",
                caption="Fig. 1.6: (a) ice to water,\n(b) water to vapour",
                confidence=0.7,
                status=MatchStatus.MATCHED,
                method=MatchMethod.NATIVE_TEXT,
            ),
            "page_02_image_01": MatchResult(
                image_id="page_02_image_01", caption=None, confidence=0.0,
                status=MatchStatus.CAPTION_NOT_FOUND,
                method=MatchMethod.NO_RELIABLE_CANDIDATE,
            ),
        }
        target = tmp_path / "results.csv"
        write_results_csv(target, extraction, results)
        with open(target, encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
        assert len(rows) == 3  # header + 2 rows, embedded newline preserved
        assert rows[1][2] == "Fig. 1.6: (a) ice to water,\n(b) water to vapour"

    def test_caption_not_found_row_has_empty_caption(self, tmp_path):
        target = tmp_path / "results.csv"
        write_results_csv(target, make_extraction(), make_results())
        with open(target, encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
        assert rows[2][2] == ""
        assert rows[2][4] == "caption_not_found"
