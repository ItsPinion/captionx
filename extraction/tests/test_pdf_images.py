"""Tests for native image extraction: placements, clustering, classification,
pixel extraction (plan.md §10.3 / §12)."""

from pathlib import Path

import pymupdf

from src.pdf import (
    FigureKind,
    cluster_placements,
    collect_placements,
    extract_standalone_png,
    render_region_png,
)
from src.pdf.extractor import extract_page
from tests.pdf_fixtures import add_text, new_page, place_image, solid_png


class TestCollectPlacements:
    def test_single_image_placement(self):
        doc, page = new_page()
        place_image(page, (100, 100, 200, 160), solid_png(64, 48, (255, 0, 0)))
        placements = collect_placements(page)
        assert len(placements) == 1
        rect = placements[0].bbox
        # pymupdf preserves aspect ratio: 64x48px in a 100x60pt rect → 80x60pt,
        # centered horizontally (110..190) and full-height (100..160).
        assert (rect.x0, rect.y0, rect.x1, rect.y1) == (110, 100, 190, 160)
        assert placements[0].xref > 0
        assert (placements[0].pixel_width, placements[0].pixel_height) == (64, 48)

    def test_no_images_empty(self):
        _doc, page = new_page()
        assert collect_placements(page) == []


class TestClustering:
    def _placed(self, rects):
        return [
            type("P", (), {"bbox": pymupdf.Rect(*r), "xref": 1, "pixel_width": 10, "pixel_height": 10})()
            for r in rects
        ]

    def test_nearby_placements_merge(self):
        # 8pt apart → merged with the default 12pt gap
        clusters = cluster_placements(
            self._placed([(100, 100, 150, 150), (158, 100, 208, 150)])
        )
        assert len(clusters) == 1

    def test_distant_placements_stay_separate(self):
        # 50pt apart → separate clusters
        clusters = cluster_placements(
            self._placed([(100, 100, 150, 150), (200, 100, 250, 150)])
        )
        assert len(clusters) == 2

    def test_transitive_merge(self):
        # a-b overlap, b-c overlap → one cluster of three
        clusters = cluster_placements(
            self._placed([(0, 0, 50, 50), (45, 0, 95, 50), (90, 0, 140, 50)])
        )
        assert len(clusters) == 1
        assert len(clusters[0].members) == 3

    def test_cluster_bbox_is_union(self):
        clusters = cluster_placements(
            self._placed([(10, 10, 50, 50), (60, 40, 100, 80)])
        )
        assert len(clusters) == 1
        bbox = clusters[0].bbox
        assert (bbox.x0, bbox.y0, bbox.x1, bbox.y1) == (10, 10, 100, 80)


class TestClassification:
    def test_standalone_real_image(self):
        doc, page = new_page()
        place_image(page, (100, 100, 250, 250), solid_png(200, 200, (0, 255, 0)))
        result = extract_page(doc, 1, "test_doc")
        assert len(result.figures) == 1
        fig = result.figures[0]
        assert fig.kind is FigureKind.STANDALONE
        assert fig.occurrence.filename == "test_doc_page_01_image_01.png"
        # exact source pixels preserved
        assert fig.png[:8] == b"\x89PNG\r\n\x1a\n"
        assert (fig.occurrence.width, fig.occurrence.height) == (200, 200)

    def test_tile_collage_becomes_single_composite(self):
        """The NCERT pattern: a figure assembled from many small strips."""
        doc, page = new_page()
        png = solid_png(8, 8, (0, 0, 255))
        # 5 x 5 grid of 12x12pt strips with small gaps, far from page edges
        for row in range(5):
            for col in range(5):
                x = 150 + col * 14
                y = 200 + row * 14
                place_image(page, (x, y, x + 12, y + 12), png)
        result = extract_page(doc, 1, "test_doc")
        assert len(result.figures) == 1
        fig = result.figures[0]
        assert fig.kind is FigureKind.COMPOSITE
        # rendered at 2x zoom from a ~66pt region → >= 100px
        assert fig.occurrence.width >= 100
        # bbox equals the strip union (plus small render padding)
        assert fig.occurrence.bbox.x0 == 150
        assert fig.occurrence.bbox.y0 == 200

    def test_edge_touching_cluster_dropped_as_decoration(self):
        doc, page = new_page()
        png = solid_png(40, 40, (255, 255, 0))
        place_image(page, (0, 300, 80, 380), png)  # touches left edge x0=0
        result = extract_page(doc, 1, "test_doc")
        assert result.figures == []

    def test_tiny_cluster_dropped(self):
        doc, page = new_page()
        png = solid_png(6, 6, (255, 0, 255))
        place_image(page, (300, 300, 306, 306), png)  # 6pt dot, not near edge
        result = extract_page(doc, 1, "test_doc")
        assert result.figures == []

    def test_occurrences_in_reading_order_and_indexed(self):
        doc, page = new_page()
        png = solid_png(100, 100, (0, 128, 255))
        place_image(page, (100, 400, 200, 500), png)  # lower-left
        place_image(page, (300, 100, 400, 200), png)  # upper-right
        result = extract_page(doc, 1, "test_doc")
        assert [f.occurrence.index for f in result.figures] == [1, 2]
        # y-sorted: the upper figure first
        assert result.figures[0].occurrence.bbox.y0 == 100
        assert result.figures[1].occurrence.bbox.y0 == 400

    def test_no_deduplication_same_image_twice(self):
        """plan.md §12: same image on the same page → two records."""
        doc, page = new_page()
        png = solid_png(100, 100, (10, 10, 10))
        place_image(page, (100, 100, 200, 200), png)
        place_image(page, (300, 300, 400, 400), png)  # same xref
        result = extract_page(doc, 1, "test_doc")
        assert len(result.figures) == 2
        assert result.figures[0].occurrence.image_id != result.figures[1].occurrence.image_id


class TestPixelExtraction:
    def test_extract_standalone_png_returns_exact_pixels(self):
        doc, page = new_page()
        place_image(page, (50, 50, 114, 114), solid_png(64, 64, (17, 34, 51)))
        xref = collect_placements(page)[0].xref
        png, (w, h) = extract_standalone_png(doc, xref)
        assert (w, h) == (64, 64)
        assert png[:8] == b"\x89PNG\r\n\x1a\n"

    def test_render_region_zoom_matches_bbox(self):
        doc, page = new_page()
        png, (w, h) = render_region_png(page, pymupdf.Rect(100, 100, 200, 150), zoom=2.0)
        # 2pt padding per side → 104x54pt at 2x → 208x108px
        assert (w, h) == (208, 108)
        assert png[:8] == b"\x89PNG\r\n\x1a\n"


class TestPageExtractionIntegration:
    def test_pages_are_one_based_and_complete(self):
        doc, _page = new_page()
        doc.new_page()  # second page
        place_image(doc[1], (100, 100, 200, 200), solid_png(80, 80, (1, 2, 3)))
        result_p2 = extract_page(doc, 2, "d")
        assert result_p2.page == 2
        assert len(result_p2.figures) == 1
        assert result_p2.figures[0].occurrence.filename == "d_page_02_image_01.png"

    def test_stem_sanitized_for_filenames(self):
        from src.pdf.extractor import sanitize_stem

        assert sanitize_stem("jesc1ps.pdf") == "jesc1ps"
        assert sanitize_stem("my book: chapter 1.pdf") == "my_book__chapter_1"
        assert sanitize_stem("___") == "document"
