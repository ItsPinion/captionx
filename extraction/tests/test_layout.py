"""PP-DocLayout-S integration (final plan §11) — unit tests with a fake model."""

from __future__ import annotations

import pymupdf
import pytest

from src.models import BBox, LayoutRegion, TextRegion, TextSource
from src.ocr.layout import CAPTION_LABELS, IMAGE_LABELS, LayoutEngine
from src.pdf.extractor import PageExtraction
from src.pipeline import _count_uncovered_figures, _tag_caption_regions


def _fake_engine(regions: list[LayoutRegion]) -> LayoutEngine:
    """A LayoutEngine whose model returns canned regions (no weights needed)."""
    engine = object.__new__(LayoutEngine)
    engine.model_dir = None
    engine._model = None
    engine._canned = regions
    return engine


def test_detect_pixmap_converts_pixels_to_points_and_filters_labels():
    engine = _fake_engine([])
    import numpy as np

    class FakeModel:
        def predict(self, image, layout_nms=True):
            # 150 dpi → scale 2.0833: box at (200, 400, 600, 800) px = (96, 192, 288, 384) pt
            return iter(
                [
                    {
                        "boxes": [
                            {"label": "image", "score": 0.9, "coordinate": [200, 400, 600, 800]},
                            {"label": "text", "score": 0.99, "coordinate": [0, 0, 100, 100]},
                            {"label": "figure_title", "score": 0.6, "coordinate": [200, 820, 500, 840]},
                            {"label": "header", "score": 0.8, "coordinate": [0, 10, 100, 30]},
                        ]
                    }
                ]
            )

    engine._model = FakeModel()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100))
    regions = engine.detect_pixmap(pix, dpi=150)
    labels = [r.label for r in regions]
    # only task-relevant labels flow onward (§11)
    assert labels == ["image", "figure_title"]
    assert regions[0].bbox.to_list() == pytest.approx([96.0, 192.0, 288.0, 384.0])
    assert regions[0].confidence == pytest.approx(0.9)


def test_tag_caption_regions_sets_layout_label_on_contained_blocks():
    page = PageExtraction(page=1)
    page.layout_regions = [
        LayoutRegion(label="figure_title", confidence=0.66, bbox=BBox(350, 494, 492, 508)),
        LayoutRegion(label="image", confidence=0.82, bbox=BBox(310, 300, 520, 490)),
    ]
    inside = TextRegion(
        text="Fig. 5.1: Compound microscope",
        bbox=BBox(355, 496, 480, 507),
        source=TextSource.NATIVE_PDF,
        page=1,
    )
    outside = TextRegion(
        text="body text far away",
        bbox=BBox(60, 100, 200, 130),
        source=TextSource.NATIVE_PDF,
        page=1,
    )
    page.text_regions = [inside, outside]
    _tag_caption_regions(page)
    assert inside.layout_label == "figure_title"
    assert inside.layout_confidence == pytest.approx(0.66)
    assert outside.layout_label is None


def test_count_uncovered_figures_flags_vector_scope_regions():
    page = PageExtraction(page=1)
    page.layout_regions = [
        LayoutRegion(label="image", confidence=0.9, bbox=BBox(50, 50, 150, 150)),
        LayoutRegion(label="image", confidence=0.8, bbox=BBox(300, 400, 500, 600)),
    ]
    from src.pdf.extractor import ExtractedFigure, FigureKind
    from src.models import ImageOccurrence

    occ = ImageOccurrence(page=1, index=1, width=10, height=10, filename="x.png")
    occ.bbox = BBox(50, 50, 150, 150)  # covers region 1 only
    page.figures = [ExtractedFigure(occurrence=occ, png=b"", kind=FigureKind.STANDALONE)]
    assert _count_uncovered_figures(page) == 1


def test_layout_labels_lift_the_layout_bucket():
    """§11/§15: a figure_title block floors the layout feature and the bucket."""
    from src.matching.features import annotate_candidate
    from src.matching.scorer import layout_feature
    from src.models import CaptionCandidate, ImageOccurrence

    image = ImageOccurrence(page=1, index=1, width=10, height=10, filename="x.png")
    image.bbox = BBox(50, 50, 150, 150)
    plain = CaptionCandidate(
        # imperfect geometry (half outside the image column) so the plain
        # layout blend lands below the floor: 0.5·1.0 + 0.5·0.5 = 0.75
        text="Fig. 1.1: A thing",
        bbox=BBox(100, 155, 300, 165),
        source=TextSource.NATIVE_PDF,
        image_id=image.image_id,
    )
    flagged = CaptionCandidate(
        text="Fig. 1.1: A thing",
        bbox=BBox(55, 155, 145, 165),
        source=TextSource.NATIVE_PDF,
        image_id=image.image_id,
        layout_label="figure_title",
    )
    annotate_candidate(image, plain)
    annotate_candidate(image, flagged)
    assert "layout_caption" not in plain.features
    assert flagged.features["layout_caption"] == 1.0
    # the §15 layout bucket the scorer consumes reflects the floor
    assert layout_feature(flagged.features) >= 0.95
    assert layout_feature(plain.features) < 0.95


def test_constants_are_the_task_relevant_labels():
    assert IMAGE_LABELS == frozenset({"image"})
    assert CAPTION_LABELS == frozenset({"figure_title"})


def test_missing_model_files_raise_clear_error(tmp_path):
    with pytest.raises(Exception, match="PP-DocLayout-S model files missing"):
        LayoutEngine(model_dir=tmp_path)
