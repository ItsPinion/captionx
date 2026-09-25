"""Tests for Phase 8 — caption-matching features (plan.md §14)."""

import pytest

from src.models import BBox
from src.matching.features import (
    FEATURE_CONFIG,
    FEATURE_NAMES,
    FeatureConfig,
    compute_features,
)


def feats(img, region, text, cfg=FEATURE_CONFIG) -> dict[str, float]:
    return compute_features(img, region, text, cfg)


def close(a: float, b: float) -> bool:
    return abs(a - b) < 1e-6


# Geometry helpers: image at (100,100)-(300,400); caption just below.
IMG = BBox(100, 100, 300, 400)


class TestFeatureContract:
    def test_all_named_features_present(self):
        f = feats(IMG, BBox(110, 410, 290, 430), "Fig. 5.6: Plant cell")
        assert tuple(f.keys()) == FEATURE_NAMES

    def test_values_in_unit_range(self):
        f = feats(IMG, BBox(0, 0, 595, 30), "extremely long " * 40)
        assert all(0.0 <= v <= 1.0 for v in f.values())


class TestProximity:
    def test_touching_gap_is_full_score(self):
        f = feats(IMG, BBox(110, 400, 290, 412), "caption")  # gap 0
        assert close(f["proximity"], 1.0)

    def test_measured_caption_gap(self):
        # Real case: 13.7pt below a figure → high but not full
        f = feats(IMG, BBox(110, 413.7, 290, 425), "Fig. 1.2")
        assert 0.8 < f["proximity"] < 1.0

    def test_far_below_decays_to_zero(self):
        f = feats(IMG, BBox(110, 500, 290, 512), "distant text")  # gap 100
        assert close(f["proximity"], 0.0)

    def test_above_uses_larger_window(self):
        # gap 100 above → (1 - 100/150); same gap below → 0
        above = feats(IMG, BBox(110, -12, 290, 0), "above text")
        assert close(above["proximity"], 1 - 100 / 150)


class TestAlignment:
    def test_perfectly_centered(self):
        f = feats(IMG, BBox(120, 410, 280, 430), "centered caption")
        assert close(f["alignment"], 1.0)

    def test_off_center_decays(self):
        f = feats(IMG, BBox(300, 410, 460, 430), "shifted right")
        delta = abs(200 - 380)  # 180 > max delta
        assert close(f["alignment"], 0.0)

    def test_real_caption_alignment_high(self):
        """Fig 1.6 caption (x0 299) under figure (326-439): centers ~27pt apart."""
        fig = BBox(326, 223, 439, 409)
        cap = BBox(299, 420, 460, 442)
        f = feats(fig, cap, "Fig. 1.6: (a) Conversion of ice to water")
        assert f["alignment"] > 0.8


class TestOverlap:
    def test_full_containment(self):
        f = feats(IMG, BBox(120, 410, 280, 430), "narrow caption")
        assert close(f["overlap"], 1.0)

    def test_half_width(self):
        f = feats(IMG, BBox(200, 410, 400, 430), "half overlapping")
        assert close(f["overlap"], 0.5)

    def test_disjoint_columns(self):
        f = feats(IMG, BBox(400, 410, 560, 430), "other column")
        assert close(f["overlap"], 0.0)


class TestPosition:
    def test_below_full(self):
        f = feats(IMG, BBox(110, 410, 290, 430), "below")
        assert close(f["position"], 1.0)

    def test_above_secondary(self):
        f = feats(IMG, BBox(110, 60, 290, 90), "above")
        assert close(f["position"], FEATURE_CONFIG.position_above)


class TestKeyword:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Fig. 5.6: Plant cell", 1.0),
            ("figure 12 - waves", 1.0),
            ("Diagram of a bell jar", 1.0),
            ("the setup is shown in Fig. 12.8", 0.6),
            ("Plant cell with organelles", 0.0),
            ("configuration of the apparatus", 0.0),  # no false 'fig' hit
        ],
    )
    def test_keyword_strength(self, text, expected):
        f = feats(IMG, BBox(110, 410, 290, 430), text)
        assert close(f["keyword"], expected)


class TestNumbering:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Fig. 5.6: Plant cell", 1.0),  # chapter.number
            ("Fig.12.13: Stethoscope", 1.0),  # no space variant
            ("Fig 12.12:  A megaphone and a horn.", 1.0),  # no dot variant
            ("Figure 3.1 something", 1.0),
            ("Fig. 1.3", 1.0),  # bare with chapter number
            ("Fig. 1.4", 1.0),
            ("shown in Fig. 12.8 above", 0.4),  # mid-text reference
            ("Activity _____________ 1.12", 0.0),
            ("Exercises", 0.0),
            ("(a)", 0.0),
        ],
    )
    def test_numbering_strength(self, text, expected):
        f = feats(IMG, BBox(110, 410, 290, 430), text)
        assert close(f["numbering"], expected)


class TestSublabel:
    @pytest.mark.parametrize("text", ["(a)", "(b)", "(ii)", "(iv)", "(A)"])
    def test_sublabels_detected(self, text):
        f = feats(IMG, BBox(110, 410, 290, 430), text)
        assert close(f["sublabel"], 1.0)

    @pytest.mark.parametrize("text", ["Fig. 1.6: (a) and (b)", "a", "(a) label text"])
    def test_non_standalone_not_sublabel(self, text):
        f = feats(IMG, BBox(110, 410, 290, 430), text)
        assert close(f["sublabel"], 0.0)


class TestTextShape:
    def test_ideal_length_full(self):
        f = feats(IMG, BBox(110, 410, 290, 430), "Fig. 5.6: Plant cell")
        assert close(f["text_shape"], 1.0)

    def test_very_short_penalty(self):
        f = feats(IMG, BBox(110, 410, 290, 430), "(a)")
        assert close(f["text_shape"], FEATURE_CONFIG.shape_short_floor)

    def test_long_body_decays(self):
        body = "word " * 80  # 400 chars
        f = feats(IMG, BBox(110, 410, 290, 430), body)
        assert f["text_shape"] < 0.6

    def test_extremely_long_decays_to_zero(self):
        body = "word " * 130  # 650 chars > 200 + 400 decay
        f = feats(IMG, BBox(110, 410, 290, 430), body)
        assert close(f["text_shape"], 0.0)

    def test_many_lines_decay(self):
        text = "\n".join(["line"] * 8)  # 8 lines ≥ min
        f = feats(IMG, BBox(110, 410, 290, 430), text)
        assert close(f["text_shape"], 0.0)


class TestAnnotateCandidates:
    def test_annotate_fills_features(self):
        from src.models import CaptionCandidate, ImageOccurrence

        image = ImageOccurrence(
            page=1, index=1, width=200, height=300,
            filename="d_page_01_image_01.png", bbox=IMG,
        )
        candidate = CaptionCandidate(
            text="Fig. 5.6: Plant cell",
            bbox=BBox(110, 410, 290, 430),
            source="native_pdf",
            image_id=image.image_id,
        )
        from src.matching.features import annotate_candidates

        annotate_candidates(image, [candidate])
        assert tuple(candidate.features.keys()) == FEATURE_NAMES
        assert candidate.features["keyword"] == 1.0
        assert candidate.features["numbering"] == 1.0

    def test_annotate_requires_bbox(self):
        from src.models import CaptionCandidate, ImageOccurrence

        image = ImageOccurrence(page=1, index=1, width=1, height=1, filename="x.png")
        candidate = CaptionCandidate(
            text="t", bbox=BBox(0, 0, 1, 1), source="ocr", image_id=image.image_id
        )
        from src.matching.features import annotate_candidate

        with pytest.raises(ValueError):
            annotate_candidate(image, candidate)

    def test_custom_config_respected(self):
        cfg = FeatureConfig(position_above=0.9, align_max_delta_pt=10)
        f = feats(IMG, BBox(110, 60, 290, 90), "above", cfg)
        assert close(f["position"], 0.9)
