"""Fixture-gated integration test for the full matcher (Phases 9–11).

Pins the expected final verdicts on the three real NCERT chapters, so
Phase 32 tuning cannot silently regress them. Skipped when the fixture PDFs
are absent (fetch with `fixtures/download.sh`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.matching import match_document
from src.models import MatchMethod, MatchStatus
from src.pdf import extract_document

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

CHAPTERS = {
    "ch01": FIXTURES / "ncert_class9_science_ch01_matter.pdf",
    "ch05": FIXTURES / "ncert_class9_science_ch05_cell.pdf",
    "ch12": FIXTURES / "ncert_class9_science_ch12_sound.pdf",
}

pytestmark = pytest.mark.skipif(
    not all(p.exists() for p in CHAPTERS.values()),
    reason="fixture PDFs missing — run extraction/fixtures/download.sh",
)


@pytest.fixture(scope="module")
def results():
    out = {}
    for key, pdf in CHAPTERS.items():
        extraction = extract_document(pdf, document_id=f"test-{key}")
        out[key] = match_document(extraction)
    return out


def find(results, chapter, page, index):
    image_id = f"page_{page:02d}_image_{index:02d}"
    assert image_id in results[chapter], f"{image_id} not in {chapter} results"
    return results[chapter][image_id]


class TestStrictMatchesHold:
    def test_simple_below_captions(self, results):
        assert find(results, "ch05", 6, 1).caption.startswith("Fig. 5.4")
        assert find(results, "ch05", 7, 1).caption.startswith("Fig. 5.5")
        assert find(results, "ch12", 2, 1).caption.startswith("Fig. 12.4")
        assert find(results, "ch01", 8, 1).caption.startswith("Fig. 1.7")

    def test_strict_methods_are_native_or_ocr(self, results):
        r = find(results, "ch05", 6, 1)
        assert r.method in (MatchMethod.NATIVE_TEXT, MatchMethod.OCR)


class TestFallbackRescues:
    def test_fig_1_5_far_below(self, results):
        r = find(results, "ch01", 5, 2)
        assert r.caption and r.caption.startswith("Fig.1.5")
        assert r.method is MatchMethod.FALLBACK

    def test_fig_1_10_shared(self, results):
        r = find(results, "ch01", 13, 2)
        assert r.caption and r.caption.startswith("Fig. 1.10")

    def test_fig_12_8_above(self, results):
        r = find(results, "ch12", 5, 1)
        assert r.caption and r.caption.startswith("Fig. 12.8")

    def test_fig_12_12_stacked(self, results):
        r = find(results, "ch12", 10, 1)
        assert r.caption and r.caption.startswith("Fig 12.12")

    def test_fig_1_6_series_passthrough(self, results):
        r = find(results, "ch01", 6, 1)
        assert r.caption and r.caption.startswith("Fig. 1.6")
        assert r.method is MatchMethod.FALLBACK


class TestCaptionlessFigures:
    def test_decorative_and_portrait_figures_not_found(self, results):
        for chapter, page, index in [
            ("ch01", 10, 1),  # Einstein portrait
            ("ch01", 12, 1),  # Exercises corner art
            ("ch01", 13, 1),  # Group Activity art
            ("ch05", 8, 1),  # Golgi portrait
            ("ch05", 10, 1),  # Exercises corner art
            ("ch12", 15, 1),  # Exercises corner art
        ]:
            r = find(results, chapter, page, index)
            assert r.status is MatchStatus.CAPTION_NOT_FOUND, (chapter, page, index)
            assert r.caption is None
            assert r.method is MatchMethod.NO_RELIABLE_CANDIDATE


class TestGlobalCounts:
    """Pinned pipeline behavior — update deliberately during Phase 32 tuning."""

    def test_counts(self, results):
        total = sum(len(r) for r in results.values())
        matched = sum(
            1 for r in results.values() for m in r.values() if m.status is MatchStatus.MATCHED
        )
        not_found = total - matched
        assert total == 31
        assert matched == 25
        assert not_found == 6

    def test_all_matched_have_captions_and_confidence(self, results):
        for chapter, per_image in results.items():
            for image_id, m in per_image.items():
                if m.status is MatchStatus.MATCHED:
                    assert m.caption, (chapter, image_id)
                    assert m.confidence > 0.5, (chapter, image_id)
                    assert m.method is not MatchMethod.NO_RELIABLE_CANDIDATE
