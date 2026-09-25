"""DL-driven matching authority (final plan §11, delta 2).

PP-DocLayout-S output decides parts of matching — not just a scoring floor:

1. merged captions inherit the head's `figure_title` tag (§38 × §11);
2. a tagged block is ADMITTED beyond the strict windows, within sanity
   bounds (the model vouches for caption-ness; geometry keeps ownership);
3. a layout `figure` region beyond the image soft-barriers below-candidates
   that start at/beyond it (they belong to the NEXT figure);
4. the matcher arbitrates near-ties toward DL-confirmed candidates.

All tests use a fake layout (plain `LayoutRegion`s) — no model weights.
"""

from __future__ import annotations

import pytest

from src.models import BBox, CaptionCandidate, ImageOccurrence, LayoutRegion, TextRegion, TextSource
from src.matching.candidates import (
    CANDIDATE_CONFIG,
    CandidateConfig,
    collect_candidates,
    merge_split_captions,
    tag_layout_barriers,
)
from src.matching.matcher import _arbitrate, match_image

NATIVE = TextSource.NATIVE_PDF


def _image(bbox: BBox) -> ImageOccurrence:
    return ImageOccurrence(
        page=1, index=1, width=int(bbox.width), height=int(bbox.height),
        filename="doc_page_01_image_01.png", bbox=bbox,
    )


def _region(text: str, bbox: BBox, *, label: str | None = None, page: int = 1) -> TextRegion:
    return TextRegion(
        text=text, bbox=bbox, source=NATIVE, page=page,
        layout_label=label, layout_confidence=0.9 if label else None,
    )


def _caption_candidate(text: str, bbox: BBox, score: float, *, barrier=False, tagged=False):
    c = CaptionCandidate(text=text, bbox=bbox, source=NATIVE, image_id="page_01_image_01")
    c.score = score
    c.features = {}
    if barrier:
        c.features["beyond_layout_barrier"] = 1.0
    if tagged:
        c.features["layout_caption"] = 1.0
    return c


class TestMergedCaptionInheritsTag:
    def test_head_tag_survives_the_merge(self):
        head = _region("Fig. 1.2: Sublimation of", BBox(60, 300, 300, 312), label="figure_title")
        cont = _region("ammonium chloride", BBox(60, 313, 280, 324))
        merged = merge_split_captions([head, cont])
        assert len(merged) == 1
        assert merged[0].layout_label == "figure_title"
        assert merged[0].layout_confidence == pytest.approx(0.9)

    def test_untagged_merge_stays_untagged(self):
        head = _region("Fig. 1.2: Sublimation of", BBox(60, 300, 300, 312))
        cont = _region("ammonium chloride", BBox(60, 313, 280, 324))
        merged = merge_split_captions([head, cont])
        assert merged[0].layout_label is None


class TestLayoutAdmission:
    """A figure_title-tagged block is admitted beyond the strict windows."""

    image = _image(BBox(60, 200, 540, 500))

    def test_beyond_window_tagged_admitted(self):
        # 130 pt below the image — outside the 100 pt window, inside 1.5×
        regions = [_region("Fig. 9.1: A deep caption", BBox(60, 630, 400, 642), label="figure_title")]
        out = collect_candidates(self.image, regions, page_height=842.0)
        assert [c.text for c in out] == ["Fig. 9.1: A deep caption"]
        assert out[0].layout_label == "figure_title"

    def test_beyond_window_untagged_rejected(self):
        regions = [_region("Fig. 9.1: A deep caption", BBox(60, 630, 400, 642))]
        assert collect_candidates(self.image, regions, page_height=842.0) == []

    def test_far_tagged_rejected_even_by_dl(self):
        # 300 pt below — beyond even the 1.5× admission bound
        regions = [_region("Fig. 9.1: A far caption", BBox(60, 800, 400, 812), label="figure_title")]
        assert collect_candidates(self.image, regions, page_height=842.0) == []

    def test_tagged_but_other_column_rejected(self):
        # within the admission gap but beside the image: no x-overlap and the
        # 60 pt x-gap exceeds the 40 pt slack — the DL tag cannot conjure a column
        regions = [_region("Fig. 9.2: Other column", BBox(600, 630, 700, 642), label="figure_title")]
        assert collect_candidates(self.image, regions, page_height=842.0) == []

    def test_in_window_tagged_still_needs_column_ownership(self):
        # 30 pt below (in-window) but 60 pt beside the image: geometry keeps
        # ownership even for tagged blocks (the tag vouches caption-ness only)
        regions = [_region("Fig. 9.2: Beside", BBox(600, 530, 700, 542), label="figure_title")]
        assert collect_candidates(self.image, regions, page_height=842.0) == []

    def test_admission_respects_fallback_cfg(self):
        # fallback windows are 160/80 → admission bound 240 below, 120 above
        cfg = CandidateConfig(max_below_gap_pt=160.0, max_above_gap_pt=80.0)
        above = _region("Fig. 9.3: High caption", BBox(60, 90, 400, 102), label="figure_title")
        out = collect_candidates(self.image, [above], page_height=842.0, cfg=cfg)
        assert len(out) == 1
        # …but the strict config's bound is 90 — out of reach there
        assert collect_candidates(self.image, [above], page_height=842.0) == []


class TestLayoutBarriers:
    image = _image(BBox(60, 200, 540, 500))
    layout = [LayoutRegion(label="image", confidence=0.9, bbox=BBox(60, 610, 540, 820))]

    def _candidate(self, y0: float) -> CaptionCandidate:
        return _caption_candidate("Fig. 9.9: X", BBox(80, y0, 400, y0 + 12), score=0.8)

    def test_candidate_at_next_figure_barrier_tagged(self):
        cands = [self._candidate(615)]  # starts below the next figure's top (610)
        tag_layout_barriers(self.image.bbox, cands, self.layout)
        assert cands[0].features["beyond_layout_barrier"] == 1.0

    def test_candidate_before_figure_not_barriered(self):
        cands = [self._candidate(560)]  # above the next figure's top
        tag_layout_barriers(self.image.bbox, cands, self.layout)
        assert "beyond_layout_barrier" not in cands[0].features

    def test_other_column_figure_is_no_barrier(self):
        layout = [LayoutRegion(label="image", confidence=0.9, bbox=BBox(560, 610, 800, 820))]
        cands = [self._candidate(620)]
        tag_layout_barriers(self.image.bbox, cands, layout)
        assert "beyond_layout_barrier" not in cands[0].features

    def test_no_layout_regions_no_flag(self):
        cands = [self._candidate(615)]
        tag_layout_barriers(self.image.bbox, cands, [])
        assert "beyond_layout_barrier" not in cands[0].features


class TestArbitration:
    def test_barriered_top_loses_near_tie_to_clean(self):
        top = _caption_candidate("Fig. 9.1: next fig", BBox(80, 620, 400, 632), 0.80, barrier=True)
        clean = _caption_candidate("Fig. 9.0: ours", BBox(80, 510, 400, 522), 0.70)
        assert _arbitrate([top, clean])[0] is clean

    def test_barriered_top_kept_when_margin_clear(self):
        top = _caption_candidate("Fig. 9.1: next fig", BBox(80, 620, 400, 632), 0.90, barrier=True)
        clean = _caption_candidate("Fig. 9.0: ours", BBox(80, 510, 400, 522), 0.70)
        assert _arbitrate([top, clean])[0] is top

    def test_tagged_wins_score_tie(self):
        top = _caption_candidate("body-ish?", BBox(80, 510, 400, 522), 0.78)
        tagged = _caption_candidate("Fig. 9.1: dl-confirmed", BBox(80, 512, 400, 524), 0.76, tagged=True)
        assert _arbitrate([top, tagged])[0] is tagged

    def test_tagged_does_not_win_clear_margin(self):
        top = _caption_candidate("strong untagged", BBox(80, 510, 400, 522), 0.90)
        tagged = _caption_candidate("Fig. 9.1: dl", BBox(80, 512, 400, 524), 0.76, tagged=True)
        assert _arbitrate([top, tagged])[0] is top

    def test_no_features_is_noop(self):
        a = _caption_candidate("a", BBox(80, 510, 400, 522), 0.8)
        b = _caption_candidate("b", BBox(80, 512, 400, 524), 0.7)
        assert _arbitrate([a, b])[0] is a
        single = _caption_candidate("solo", BBox(80, 510, 400, 522), 0.5)
        assert _arbitrate([single]) == [single]


class TestEndToEndNoRegression:
    def test_plain_page_unchanged_without_layout(self):
        image = _image(BBox(60, 200, 540, 500))
        regions = [
            _region("Some body text that rambles on and on in the same column", BBox(60, 150, 540, 190)),
            _region("Fig. 9.1: The caption", BBox(60, 510, 400, 522), label="figure_title"),
        ]
        result = match_image(image, regions, page_height=842.0)
        assert result is not None and result.status.value == "matched"
        assert result.caption == "Fig. 9.1: The caption"

    def test_admitted_dl_caption_rescues_match(self):
        # caption 200 pt below the image: outside the FALLBACK window (160 pt)
        # and every strict window — only the DL admission (240 pt bound in the
        # fallback pass) can reach it
        image = _image(BBox(60, 200, 540, 500))
        plain = [
            _region("Fig. 9.1: The deep caption", BBox(60, 700, 400, 712)),
            _region("Fig. 9.9: other figure", BBox(60, 760, 400, 772)),
        ]
        unmatched = match_image(image, plain, page_height=842.0)
        assert unmatched is None or unmatched.status.value == "caption_not_found"
        tagged = [
            _region("Fig. 9.1: The deep caption", BBox(60, 700, 400, 712), label="figure_title"),
            _region("Fig. 9.9: other figure", BBox(60, 760, 400, 772), label="figure_title"),
        ]
        result = match_image(image, tagged, page_height=842.0)
        assert result is not None and result.status.value == "matched"
        assert result.caption == "Fig. 9.1: The deep caption"


class TestConfigDefaults:
    def test_admission_bounds_documented(self):
        cfg = CANDIDATE_CONFIG
        assert cfg.layout_admit_gap_factor == 1.5
        assert cfg.layout_admit_min_overlap == 0.25
        assert cfg.barrier_min_figure_gap_pt == 4.0
