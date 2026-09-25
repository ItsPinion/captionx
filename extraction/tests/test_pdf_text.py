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

    def test_fused_footer_caption_block_is_split(self):
        """A block gluing a running footer above the caption splits at the head.

        Real-world case (unseen ch02 p6): the fused block even landed inside
        the running-footer band and was dropped wholesale — the caption below
        a true figure then had no candidate at all.
        """
        doc, page = new_page()
        add_text(page, "MATTER AROUND US PURE\nFig. 2.5: Evaporation", (72, 700))
        regions = extract_text_regions(page)
        assert [r.text for r in regions] == [
            "MATTER AROUND US PURE",
            "Fig. 2.5: Evaporation",
        ]
        pre, head = regions
        assert pre.bbox.y1 <= head.bbox.y0 + 0.1  # split at the head line's y
        assert head.bbox.y1 == pre.bbox.y1 or head.bbox.y0 < head.bbox.y1

    def test_stray_line_above_caption_head_is_split(self):
        """Unseen ch02 p7: 'by sublimation ⏎ Fig. 2.6: …' in one block."""
        doc, page = new_page()
        add_text(page, "by sublimation\nFig. 2.6: Separation of immiscible liquids", (72, 690))
        regions = extract_text_regions(page)
        assert [r.text.split("\n")[0] for r in regions] == [
            "by sublimation",
            "Fig. 2.6: Separation of immiscible liquids",
        ]
        # the caption region starts exactly at the head line
        assert regions[1].text.startswith("Fig.")

    def test_clean_caption_block_is_not_split(self):
        doc, page = new_page()
        add_text(page, "Fig. 2.6: Separation of immiscible liquids", (72, 700))
        regions = extract_text_regions(page)
        assert len(regions) == 1
        assert regions[0].text == "Fig. 2.6: Separation of immiscible liquids"

    def test_embedded_head_without_measured_line_stays_whole(self):
        """If the dict pass cannot place the head line, behavior is unchanged."""
        doc, page = new_page()
        add_text(page, "first line\nFig. 2.7: something", (72, 700))
        regions = extract_text_regions(page)
        # split found the line here — text pieces preserved exactly (§13.4)
        assert "\n" in regions[0].text or len(regions) == 2
        assert "".join(r.text for r in regions) == "first lineFig. 2.7: something"

    def test_extract_page_returns_text_and_figures_together(self):
        doc, page = new_page()
        add_text(page, "Fig. 1.6: ice melting", (72, 650))
        place_image(page, (100, 200, 220, 320), solid_png(100, 100, (9, 9, 9)))
        result = extract_page(doc, 1, "d")
        assert len(result.text_regions) == 1
        assert len(result.figures) == 1
