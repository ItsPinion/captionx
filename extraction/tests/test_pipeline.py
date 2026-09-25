"""Tests for the pipeline orchestration (stages, outputs, error reporting)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.models import DocumentSource, MatchStatus
from src.pipeline import STAGES, StageError, run_pipeline

from tests.pdf_fixtures import add_text, new_page, place_image, solid_png

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
CELL_PDF = FIXTURES / "ncert_class9_science_ch05_cell.pdf"
pytestmark_real = pytest.mark.skipif(not CELL_PDF.exists(), reason="fixtures missing")


def make_simple_pdf(tmp_path: Path) -> Path:
    """One page: an image + its caption — the smallest real pipeline input."""
    doc, page = new_page()
    place_image(page, (100, 100, 260, 260), solid_png(120, 120, (200, 10, 10)))
    add_text(page, "Fig. 1.1: A red square of importance", (100, 280))
    path = tmp_path / "simple.pdf"
    doc.save(path)
    doc.close()
    return path


class TestStages:
    def test_happy_path_reports_all_stages_in_order(self, tmp_path):
        pdf = make_simple_pdf(tmp_path)
        seen = []
        run_pipeline(pdf, tmp_path / "out", "job_x", report=lambda s, m: seen.append(s))
        # 'ocr' reports twice (check + summary) — first occurrences follow §30 order
        deduped = list(dict.fromkeys(seen))
        assert deduped == list(STAGES)

    def test_missing_file_raises_input_stage_error(self, tmp_path):
        with pytest.raises(StageError) as excinfo:
            run_pipeline(tmp_path / "nope.pdf", tmp_path / "out", "j")
        assert excinfo.value.stage == "input"

    def test_non_pdf_magic_rejected_at_input(self, tmp_path):
        fake = tmp_path / "fake.pdf"
        fake.write_text("definitely not a pdf")
        with pytest.raises(StageError) as excinfo:
            run_pipeline(fake, tmp_path / "out", "j")
        assert excinfo.value.stage == "input"
        assert "magic" in excinfo.value.message


class TestOutputs:
    def test_simple_pdf_produces_correct_results(self, tmp_path):
        pdf = make_simple_pdf(tmp_path)
        outcome = run_pipeline(pdf, tmp_path / "out", "job_simple")

        assert outcome.image_count == 1
        assert outcome.json_path.exists()
        assert outcome.csv_path.exists()
        payload = json.loads(outcome.json_path.read_text(encoding="utf-8"))
        assert payload["document"]["filename"] == "simple.pdf"
        assert len(payload["images"]) == 1
        entry = payload["images"][0]
        assert entry["caption"] == "Fig. 1.1: A red square of importance"
        assert entry["status"] == "matched"

        # the extracted image file exists with real PNG content
        png = outcome.images_dir / entry["image"]
        assert png.exists()
        assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

    def test_filename_override_recorded(self, tmp_path):
        pdf = make_simple_pdf(tmp_path)
        outcome = run_pipeline(
            pdf, tmp_path / "out", "job_x",
            filename="display_name.pdf",
        )
        assert outcome.extraction.document.filename == "display_name.pdf"
        # image filenames use the display stem
        assert outcome.extraction.figures[0].occurrence.filename.startswith("display_name_page_01")

    def test_source_url_recorded(self, tmp_path):
        pdf = make_simple_pdf(tmp_path)
        outcome = run_pipeline(pdf, tmp_path / "out", "job_x", source="url")
        assert outcome.extraction.document.source is DocumentSource.URL


class TestRealFixturePipeline:
    @pytestmark_real
    def test_cell_chapter_end_to_end(self, tmp_path):
        outcome = run_pipeline(CELL_PDF, tmp_path / "cell", "job_cell")

        payload = json.loads(outcome.json_path.read_text(encoding="utf-8"))
        assert payload["document"]["filename"] == CELL_PDF.name
        assert payload["document"]["page_count"] == 11
        assert len(payload["images"]) == 8

        matched = [i for i in payload["images"] if i["status"] == "matched"]
        assert len(matched) == 6
        assert all(i["caption"] and i["caption"].startswith("Fig") for i in matched)

        not_found = [i for i in payload["images"] if i["status"] == "caption_not_found"]
        assert len(not_found) == 2  # Golgi portrait + 'Exercises' corner art
        assert all(i["caption"] is None for i in not_found)

        # every image entry has a file on disk
        for entry in payload["images"]:
            assert (outcome.images_dir / entry["image"]).is_file()

        # csv rows line up with json entries
        import csv as csv_mod

        with open(outcome.csv_path, encoding="utf-8", newline="") as handle:
            rows = list(csv_mod.reader(handle))
        assert len(rows) == 1 + len(payload["images"])
        assert rows[0] == ["image", "page", "caption", "confidence", "status", "method"]
