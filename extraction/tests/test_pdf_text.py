"""Tests for native text extraction (plan.md §10.4)."""

from src.pdf import extract_text_regions
from src.pdf.extractor import extract_page
from src.models import TextSource
from tests.pdf_fixtures import add_text, new_page, place_image, solid_png


class TestExtractTextRegions:
    def test_blocks_with_bboxes(self):
        doc, page = new_page()
        add_text(page, "Fig. 1.1: Three states of matter", (72, 300))
        add_text(page, "A sentence of body text.", (72, 120))
        regions = extract_text_regions(page)
        assert len(regions) == 2
        assert all(r.source is TextSource.NATIVE_PDF for r in regions)
        assert all(r.page == 1 for r in regions)
        # bboxes are in points and ordered
        for r in regions:
            assert r.bbox.x0 < r.bbox.x1
            assert r.bbox.y0 < r.bbox.y1

    def test_exact_text_preserved(self):
        """plan.md §13.4: candidate text must not be normalized."""
        doc, page = new_page()
        add_text(page, "Fig. 5.2:  Plant cell", (72, 300))
        regions = extract_text_regions(page)
        assert any(r.text == "Fig. 5.2:  Plant cell" for r in regions)

    def test_bbox_position_reflects_insertion_point(self):
        doc, page = new_page()
        add_text(page, "caption here", (200, 400), fontsize=12)
        r = extract_text_regions(page)[0]
        assert r.bbox.x0 == 200
        assert 380 < r.bbox.y0 < 400  # bbox spans above the baseline
        assert r.bbox.y1 >= 400

    def test_text_region_page_numbers_are_one_based(self):
        doc, _ = new_page()
        doc.new_page()
        add_text(doc[1], "second page text", (72, 100))
        regions = extract_text_regions(doc[1])
        assert regions[0].page == 2

    def test_extract_page_returns_text_and_figures_together(self):
        doc, page = new_page()
        add_text(page, "Fig. 1.6: ice melting", (72, 650))
        place_image(page, (100, 200, 220, 320), solid_png(100, 100, (9, 9, 9)))
        result = extract_page(doc, 1, "d")
        assert len(result.text_regions) == 1
        assert len(result.figures) == 1
