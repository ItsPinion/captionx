"""Tests for Phase 7 — caption candidate detection (plan.md §13)."""

import pytest

from src.models import BBox, CaptionCandidate, ImageOccurrence, TextRegion, TextSource
from src.matching import (
    CANDIDATE_CONFIG,
    build_page_candidates,
    collect_candidates,
    merge_split_captions,
    is_figure_internal,
    is_page_number,
    is_running_footer,
    passes_base_filters,
)
from src.pdf.extractor import PageExtraction

A4_HEIGHT = 842.0


def image(y0=100, y1=300, x0=100, x1=300, page=1, index=1) -> ImageOccurrence:
    return ImageOccurrence(
        page=page,
        index=index,
        width=200,
        height=200,
        filename=f"doc_page_{page:02d}_image_{index:02d}.png",
        bbox=BBox(x0, y0, x1, y1),
    )


def region(text, y0, x0=110, x1=290, page=1, source=TextSource.NATIVE_PDF, y1=None) -> TextRegion:
    height = 12
    return TextRegion(
        text=text,
        bbox=BBox(x0, y0, x1, y1 if y1 is not None else y0 + height),
        source=source,
        page=page,
    )


def candidates_for(image_obj, *regions, page_height=A4_HEIGHT) -> list[CaptionCandidate]:
    return collect_candidates(image_obj, list(regions), page_height=page_height)


class TestPageNumberFilter:
    @pytest.mark.parametrize("text", ["64", "— 64 —", "- 64 -", "–64–", "1234"])
    def test_page_numbers_detected(self, text):
        assert is_page_number(text)

    @pytest.mark.parametrize("text", ["Fig. 5.6", "1.2", "12 atoms", "SCIENCE 62", ""])
    def test_content_not_mistaken_for_page_number(self, text):
        assert not is_page_number(text)


class TestRunningFooterFilter:
    def test_measured_ncert_footer_band_rejected(self):
        """The real footer: y 738-747 on an 842 pt page."""
        footer = region("SCIENCE 62", y0=738, x0=74, x1=526)
        assert is_running_footer(footer.bbox, A4_HEIGHT)
        assert not passes_base_filters(footer, A4_HEIGHT)

    def test_real_caption_just_above_band_kept(self):
        """Measured: real captions end by y≈722 — 20+ pt above the band."""
        caption = region("Fig. 12.4: A beam of light...", y0=707, y1=716)
        assert passes_base_filters(caption, A4_HEIGHT)

    def test_tall_block_spanning_the_band_kept(self):
        """Only *short* blocks inside the band are furniture."""
        tall = region("a paragraph", y0=720, y1=760)
        assert passes_base_filters(tall, A4_HEIGHT)

    def test_block_below_band_kept(self):
        below = region("strapline", y0=790, y1=800)
        assert passes_base_filters(below, A4_HEIGHT)


class TestBaseFilters:
    def test_oversized_text_block_rejected(self):
        body = region("word " * 200, y0=100, y1=300)  # 1000 chars
        assert not passes_base_filters(body, A4_HEIGHT)

    def test_oversized_tall_block_rejected(self):
        body = region("columns", y0=100, y1=400)
        assert not passes_base_filters(body, A4_HEIGHT)

    def test_header_rejected(self):
        head = region("MATTER IN OUR SURROUNDINGS", y0=20, y1=32)
        assert not passes_base_filters(head, A4_HEIGHT)

    def test_empty_text_rejected(self):
        assert not passes_base_filters(region("   ", y0=400), A4_HEIGHT)


class TestFigureInternalFilter:
    def test_label_inside_figure_rejected(self):
        img = image()
        label = region("Nucleus", y0=150, x0=150, x1=220)
        assert is_figure_internal(label.bbox, img.bbox)
        cands = candidates_for(img, label)
        assert cands == []

    def test_caption_outside_figure_kept(self):
        img = image()
        caption = region("Fig. 5.6: Plant cell", y0=310)
        assert not is_figure_internal(caption.bbox, img.bbox)


class TestWindows:
    def test_caption_below_within_window(self):
        img = image(y1=300)
        cands = candidates_for(img, region("Fig. 1.6: ice to water", y0=320))
        assert len(cands) == 1
        assert cands[0].image_id == img.image_id

    def test_too_far_below_rejected(self):
        img = image(y1=300)
        assert candidates_for(img, region("distant paragraph", y0=450)) == []

    def test_caption_above_within_window(self):
        img = image(y0=300)
        # caption ends 58 pt above the image — inside the (§33-corrected) 60 pt window
        cands = candidates_for(img, region("Fig. 12.8: pressure variation", y0=230))
        assert len(cands) == 1

    def test_too_far_above_rejected(self):
        img = image(y0=300)
        assert candidates_for(img, region("far above", y0=100)) == []

    def test_window_edges_inclusive(self):
        img = image(y0=300, y1=500)
        at_below_edge = region("just below", y0=600, y1=612)  # gap == 100
        at_above_edge = region("just above", y0=228, y1=240)  # gap == 60
        cands = candidates_for(img, at_below_edge, at_above_edge)
        assert sorted(c.text for c in cands) == ["just above", "just below"]

    def test_overlapping_block_counts_as_below(self):
        """Blocks overlapping the image vertically but sticking out below."""
        img = image(y0=100, y1=300)
        sticking_out = region("(a)", y0=320, x0=210, x1=224, y1=341)
        cands = candidates_for(img, sticking_out)
        assert len(cands) == 1


class TestHorizontalRelation:
    def test_same_column_paragraph_kept(self):
        img = image(x0=100, x1=300)
        cands = candidates_for(img, region("body text under figure", x0=100, x1=295, y0=320))
        assert len(cands) == 1

    def test_other_column_rejected(self):
        img = image(x0=330, x1=540)  # right column
        left_text = region("left column body text", x0=57, x1=283, y0=320)
        assert candidates_for(img, left_text) == []

    def test_near_miss_within_slack_kept(self):
        """Measured case: `Fig. 1.4` with only 10.6 pt x-overlap."""
        img = image(x0=100, x1=300)
        indented = region("Fig. 1.4", x0=290, x1=330, y0=320)  # 10pt overlap
        assert candidates_for(img, indented) != []

    def test_far_side_text_rejected(self):
        img = image(x0=100, x1=300)
        far = region("side note", x0=450, x1=540, y0=320)
        assert candidates_for(img, far) == []


class TestCandidateProperties:
    def test_exact_text_preserved(self):
        """§13.4: no normalization of candidate text."""
        img = image()
        raw = "Fig. 5.2:  Plant cell"
        cands = candidates_for(img, region(raw, y0=320))
        assert cands[0].text == raw

    def test_source_preserved(self):
        img = image()
        ocr_cand = region("OCR caption", y0=320, source=TextSource.OCR)
        cands = candidates_for(img, ocr_cand)
        assert cands[0].source is TextSource.OCR

    def test_features_empty_at_this_stage(self):
        img = image()
        cands = candidates_for(img, region("caption", y0=320))
        assert cands[0].features == {}
        assert cands[0].score == 0.0

    def test_sorted_by_distance(self):
        img = image(y0=100, y1=300)
        near = region("near caption", y0=310)
        far = region("far caption", y0=380)
        cands = candidates_for(img, far, near)  # deliberately shuffled input
        assert [c.text for c in cands] == ["near caption", "far caption"]

    def test_same_page_restriction(self):
        """§13.1: regions from other pages are never candidates."""
        img = image(page=1)
        other_page = region("caption on page 2", y0=320, page=2)
        assert candidates_for(img, other_page) == []

    def test_image_without_bbox_has_no_candidates(self):
        img = ImageOccurrence(page=1, index=1, width=10, height=10, filename="x.png")
        assert candidates_for(img, region("caption", y0=320)) == []


class TestSharedAndStackedFigures:
    def test_two_images_each_get_candidates(self):
        top = image(y0=100, y1=300, index=1)
        bottom = image(y0=400, y1=600, index=2)
        cap_a = region("(a)", y0=320, x0=150, x1=170)
        cap_b = region("Fig. 1.6: (a) and (b) setups", y0=620)
        regions = [cap_a, cap_b]
        top_cands = collect_candidates(top, regions, page_height=A4_HEIGHT)
        bottom_cands = collect_candidates(bottom, regions, page_height=A4_HEIGHT)
        assert [c.text for c in top_cands] == ["(a)"]
        # §33: the label 68 pt above the bottom image is outside the 60 pt
        # above-window — only the caption below it is a candidate.
        assert [c.text for c in bottom_cands] == ["Fig. 1.6: (a) and (b) setups"]

    def test_shared_caption_region_reaches_both_images(self):
        """§40 case 7: two adjacent images share a caption region."""
        left = image(y0=100, y1=300, x0=60, x1=280, index=1)
        right = image(y0=100, y1=300, x0=320, x1=540, index=2)
        shared = region("Fig. 12.13: Stethoscope", y0=320, x0=150, x1=450)
        left_cands = collect_candidates(left, [shared], page_height=A4_HEIGHT)
        right_cands = collect_candidates(right, [shared], page_height=A4_HEIGHT)
        assert len(left_cands) == 1
        assert len(right_cands) == 1


class TestPageAndDocumentBuilders:
    def _page(self, *regions) -> PageExtraction:
        img = image(y0=100, y1=300, index=1)
        from src.models import MatchMethod  # noqa: F401  (import guard)

        from src.pdf.extractor import ExtractedFigure
        from src.pdf.images import FigureKind

        figure = ExtractedFigure(
            occurrence=img,
            png=b"",
            kind=FigureKind.STANDALONE,
        )
        return PageExtraction(
            page=1,
            figures=[figure],
            text_regions=list(regions),
            page_width=595.0,
            page_height=A4_HEIGHT,
        )

    def test_build_page_candidates_keys_by_image_id(self):
        page = self._page(
            region("Fig. 5.6: Plant cell", y0=320),
            region("SCIENCE 64", y0=738, x0=74, x1=526),
        )
        result = build_page_candidates(page)
        assert list(result.keys()) == ["page_01_image_01"]
        texts = [c.text for c in result["page_01_image_01"]]
        assert texts == ["Fig. 5.6: Plant cell"]  # footer filtered out

    def test_missing_page_height_raises(self):
        page = self._page()
        page.page_height = None
        with pytest.raises(ValueError):
            build_page_candidates(page)

    def test_page_without_figures_gives_empty_map(self):
        page = PageExtraction(page=1, figures=[], text_regions=[], page_width=595, page_height=842)
        assert build_page_candidates(page) == {}


class TestMergeSplitCaptions:
    """§38 split_caption fix — measured on NCERT Figs 1.2/1.5/1.6/12.6/12.8."""

    def test_joins_tight_overlapping_continuation(self):
        head = region("Fig. 1.2: Estimating how small are the particles of", y0=285.7, y1=294.7)
        cont = region("matter. With every dilution, the colour is still visible.", y0=296.5, y1=316.3)
        merged = merge_split_captions([head, cont])
        assert len(merged) == 1
        assert merged[0].text == (
            "Fig. 1.2: Estimating how small are the particles of"
            " matter. With every dilution, the colour is still visible."
        )
        # bbox is the union
        assert merged[0].bbox.y0 == 285.7
        assert merged[0].bbox.y1 == 316.3

    def test_does_not_join_neighbouring_column_text(self):
        # The measured trap: body text 2.8 pt below a caption but in the
        # other column (no x-overlap) — e.g. Fig 5.5 vs "We have talked…".
        head = region("Fig. 5.5: Animal cell", y0=621.5, y1=630.5, x0=383, x1=473)
        body = region("We have talked about the nucleus in a previous section.", y0=633.3, y1=700.0, x0=69, x1=296)
        merged = merge_split_captions([head, body])
        assert len(merged) == 2
        assert merged[0].text == "Fig. 5.5: Animal cell"

    def test_does_not_join_next_caption_or_bullet(self):
        head = region("Fig. 1.4", y0=660.6, y1=669.6, x0=164, x1=200)
        nxt = region("Fig.1.5: a, b and c show the magnified schematic", y0=677.1, y1=686.1, x0=313, x1=500)
        bullet = region("• What do you observe? In which case was the piston pushed?", y0=671.0, y1=700.0, x0=80, x1=290)
        merged = merge_split_captions([head, nxt, bullet])
        # output is y-sorted; the point is that nothing was absorbed
        assert sorted(r.text for r in merged) == sorted(
            [head.text, nxt.text, bullet.text]
        )

    def test_unrelated_blocks_kept_in_order(self):
        a = region("Fig. 12.7: Longitudinal wave in a slinky.", y0=100)
        b = region("Regular body text well below.", y0=200)
        merged = merge_split_captions([a, b])
        assert [r.text for r in merged] == [a.text, b.text]
