"""Tests for Phase 10 — confidence calculation and acceptance (plan.md §16)."""

import pytest

from src.models import BBox, CaptionCandidate, ImageOccurrence
from src.matching.confidence import (
    CONFIDENCE_CONFIG,
    caption_evidence,
    evaluate_top_candidate,
    match_confidence,
)
from src.matching.features import annotate_candidates, compute_features
from src.matching.scorer import score_candidates


def prepared(text, img_bbox, cap_bbox) -> CaptionCandidate:
    image = ImageOccurrence(
        page=1, index=1, width=200, height=300,
        filename="d_page_01_image_01.png", bbox=img_bbox,
    )
    candidate = CaptionCandidate(
        text=text, bbox=cap_bbox, source="native_pdf", image_id=image.image_id
    )
    annotate_candidates(image, [candidate])
    return candidate


def ranked_of(*candidates):
    score_candidates(list(candidates))
    return sorted(candidates, key=lambda c: c.score, reverse=True)


FIG = BBox(100, 100, 300, 400)


class TestConfidenceMath:
    def test_none_for_no_candidates(self):
        assert match_confidence([]) is None

    def test_single_candidate_uses_score_only(self):
        candidate = prepared("Fig. 5.6: Plant cell", FIG, BBox(110, 401, 290, 424))
        ranked = ranked_of(candidate)
        confidence = match_confidence(ranked)
        assert confidence == pytest.approx(
            CONFIDENCE_CONFIG.weight_score * candidate.score
            + CONFIDENCE_CONFIG.weight_margin * 1.0
        )

    def test_big_margin_boosts_confidence(self):
        strong = prepared("Fig. 5.6: Plant cell", FIG, BBox(110, 401, 290, 424))
        weak = prepared("body text under the figure", FIG, BBox(110, 430, 290, 470))
        with_close = match_confidence(ranked_of(strong, weak))
        alone = match_confidence(ranked_of(strong))
        assert with_close < alone

    def test_equal_scores_zero_margin(self):
        a = prepared("Fig. 5.6: Plant cell", FIG, BBox(110, 401, 290, 424))
        b = prepared("Fig. 5.6: Plant cell", FIG, BBox(110, 401, 290, 424))
        confidence = match_confidence(ranked_of(a, b))
        assert confidence is not None
        assert confidence == pytest.approx(CONFIDENCE_CONFIG.weight_score * a.score)

    def test_confidence_bounds(self):
        a = prepared("Fig. 5.6: Plant cell", FIG, BBox(110, 401, 290, 424))
        confidence = match_confidence(ranked_of(a))
        assert 0.0 <= confidence <= 1.0


class TestEvidence:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Fig. 5.6: Plant cell", 1.0),
            ("Fig. 1.3", 1.0),
            ("shown in Fig. 12.8 above", 0.6),  # mid-text: not strong enough
            ("body text about cells", 0.0),
            ("(a)", 0.0),
        ],
    )
    def test_evidence_strength(self, text, expected):
        features = compute_features(FIG, BBox(110, 410, 290, 430), text)
        assert caption_evidence(features) == pytest.approx(expected)


class TestAcceptance:
    def test_strong_caption_accepted(self):
        caption = prepared("Fig. 5.6: Plant cell", FIG, BBox(110, 401, 290, 424))
        noise = prepared("body text under the figure here", FIG, BBox(110, 430, 290, 470))
        best, confidence, accepted = evaluate_top_candidate(ranked_of(caption, noise))
        assert accepted is True
        assert best is caption
        assert confidence is not None and confidence > 0.6

    def test_geometry_only_winner_rejected(self):
        """The measured Einstein-portrait scene: `(1879-1955)` on top."""
        date = prepared("(1879-1955)", FIG, BBox(110, 406, 230, 415))
        para = prepared("Bose-Einstein Condensate: In 1920 ...", FIG, BBox(90, 575, 283, 602))
        best, confidence, accepted = evaluate_top_candidate(ranked_of(date, para))
        assert accepted is False  # no caption evidence, score below escape

    def test_body_text_with_figure_mention_rejected(self):
        """Mid-text `Fig. 12.8` reference: evidence 0.6 < 0.7, score < escape."""
        mention = prepared("shown in Fig. 12.8 above as density variations", FIG, BBox(56, 424, 277, 436))
        _best, _confidence, accepted = evaluate_top_candidate(ranked_of(mention))
        assert accepted is False

    def test_weak_top_score_rejected(self):
        far_caption = prepared("Fig. 1.5: schematic drawing", FIG, BBox(314, 677, 500, 710))
        _best, confidence, accepted = evaluate_top_candidate(ranked_of(far_caption))
        # real measured case: gap 95pt → weak proximity; likely rejected
        if far_caption.score < CONFIDENCE_CONFIG.min_score:
            assert accepted is False

    def test_no_candidates(self):
        best, confidence, accepted = evaluate_top_candidate([])
        assert best is None and confidence is None and accepted is False

    def test_keywordless_never_matches_on_geometry(self):
        """No figure words anywhere → no match, however perfect the geometry.

        Geometry-only scores cap at 0.75 < escape 0.78 (the `H. R. Hertz`
        trap). Keyword-less captions do not occur in the target chapters.
        """
        candidate = prepared(
            "Plant cell with all organelles labeled",
            BBox(100, 100, 300, 400),
            BBox(110, 401, 290, 421),  # touching, centered, short
        )
        _best, _confidence, accepted = evaluate_top_candidate(ranked_of(candidate))
        assert accepted is False

    def test_low_confidence_ambiguous_pair_rejected(self):
        """Two near-identical candidates split the vote (§16 'uncertain')."""
        a = prepared("Fig. 5.6: Plant cell", FIG, BBox(110, 401, 290, 424))
        b = prepared("Fig. 5.6: Plant cell diagram", FIG, BBox(112, 430, 288, 452))
        _best, confidence, accepted = evaluate_top_candidate(ranked_of(a, b))
        assert confidence is not None
        # tiny margin → confidence dragged toward the score alone; borderline
        # cases like this are exactly what the threshold guards
        assert confidence <= CONFIDENCE_CONFIG.weight_score * a.score + CONFIDENCE_CONFIG.weight_margin * 0.15
