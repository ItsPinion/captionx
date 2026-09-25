"""Tests for Phase 9 — the weighted scoring function (plan.md §15)."""

import pytest

from src.models import BBox, CaptionCandidate, ImageOccurrence
from src.matching.features import FEATURE_NAMES, annotate_candidates, compute_features
from src.matching.scorer import (
    SCORE_CONFIG,
    layout_feature,
    rank_candidates,
    score_candidate,
    score_candidates,
)


def make_candidate(text, img_bbox, cap_bbox, source="native_pdf") -> CaptionCandidate:
    image = ImageOccurrence(
        page=1, index=1, width=200, height=300,
        filename="d_page_01_image_01.png", bbox=img_bbox,
    )
    candidate = CaptionCandidate(
        text=text,
        bbox=cap_bbox,
        source=source,
        image_id=image.image_id,
    )
    annotate_candidates(image, [candidate])
    return candidate


# Measured geometry from ch01 p6: two stacked experiment figures.
FIG = BBox(331, 475, 439, 639)
CAPTION = BBox(299, 698, 460, 731)  # "Fig. 1.6: (a) Conversion of ice to water, ..."
SUBLABEL_B = BBox(407, 664, 419, 675)  # "(b)" between the figures
CONTINUATION = BBox(344, 745, 451, 754)  # "of water to water vapour"


class TestWeights:
    def test_weights_sum_to_one(self):
        total = (
            SCORE_CONFIG.proximity
            + SCORE_CONFIG.alignment
            + SCORE_CONFIG.keyword
            + SCORE_CONFIG.numbering
            + SCORE_CONFIG.text_shape
            + SCORE_CONFIG.layout
        )
        assert total == pytest.approx(1.0)

    def test_plan_example_weights(self):
        """plan.md §15 example: 40/20/15/10/10/5."""
        assert SCORE_CONFIG.proximity == 0.40
        assert SCORE_CONFIG.alignment == 0.20
        assert SCORE_CONFIG.keyword == 0.15
        assert SCORE_CONFIG.numbering == 0.10
        assert SCORE_CONFIG.text_shape == 0.10
        assert SCORE_CONFIG.layout == 0.05


class TestLayoutFeature:
    def test_blend_of_position_and_overlap(self):
        features = {"position": 1.0, "overlap": 0.5}
        assert layout_feature(features) == pytest.approx(0.75)


def make_scored(text, img_bbox, cap_bbox) -> CaptionCandidate:
    candidate = make_candidate(text, img_bbox, cap_bbox)
    score_candidate(candidate)
    return candidate


class TestScoring:
    def test_true_caption_beats_sublabel_and_continuation(self):
        """The measured ch01 p6 scene: Fig caption vs (b) vs continuation."""
        caption = make_candidate(
            "Fig. 1.6: (a) Conversion of ice to water, (b) conversion of water to water vapour",
            FIG, CAPTION,
        )
        sublabel = make_candidate("(b)", FIG, SUBLABEL_B)
        continuation = make_candidate("of water to water vapour", FIG, CONTINUATION)

        score_candidates([caption, sublabel, continuation])
        assert caption.score > sublabel.score
        assert caption.score > continuation.score
        # the demotion must hurt the sub-label meaningfully
        assert sublabel.score < 0.55

    def test_score_bounds(self):
        candidate = make_candidate("Fig. 5.6: Plant cell", FIG, CAPTION)
        assert 0.0 <= candidate.score <= 1.0

    def test_perfect_candidate_near_one(self):
        """Touching, aligned, numbered, short: near-maximum."""
        candidate = make_scored(
            "Fig. 5.6: Plant cell",
            BBox(100, 100, 300, 400),
            BBox(110, 401, 290, 424),
        )
        assert candidate.score > 0.9

    def test_requires_features(self):
        candidate = CaptionCandidate(
            text="x", bbox=BBox(0, 0, 1, 1), source="ocr", image_id="page_01_image_01"
        )
        with pytest.raises(ValueError, match="annotate"):
            score_candidate(candidate)

    def test_sublabel_demotion_applied(self):
        """Identical geometry and text shape: only the sublabel flag differs."""
        plain = make_scored("cell drawing", FIG, SUBLABEL_B)
        sub = make_scored("(b)", FIG, SUBLABEL_B)
        assert sub.score < plain.score

    def test_ranking_best_first(self):
        caption = make_scored("Fig. 1.6: conversion", FIG, CAPTION)
        continuation = make_scored("of water to water vapour", FIG, CONTINUATION)
        ranked = rank_candidates([continuation, caption])
        assert ranked[0] is caption

    def test_scores_returned_in_input_order(self):
        a = make_candidate("Fig. 1.6: conversion", FIG, CAPTION)
        b = make_candidate("of water to water vapour", FIG, CONTINUATION)
        scores = score_candidates([b, a])
        assert scores[0] == b.score
        assert scores[1] == a.score
