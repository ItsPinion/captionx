"""Tests for Phase 11 — fallback matching (plan.md §17)."""

import pytest

from src.models import BBox, ImageOccurrence, MatchMethod, MatchResult, MatchStatus, TextRegion, TextSource
from src.matching import (
    FALLBACK_CANDIDATE_CONFIG,
    FALLBACK_SCORE_CONFIG,
    match_image,
    series_passthrough,
)
from src.pdf.extractor import ExtractedFigure, PageExtraction
from src.pdf.images import FigureKind


def img(page=1, index=1, x0=100, y0=100, x1=300, y1=400) -> ImageOccurrence:
    return ImageOccurrence(
        page=page,
        index=index,
        width=int(x1 - x0),
        height=int(y1 - y0),
        filename=f"d_page_{page:02d}_image_{index:02d}.png",
        bbox=BBox(x0, y0, x1, y1),
    )


def region(text, x0, y0, x1, y1, page=1, source=TextSource.NATIVE_PDF) -> TextRegion:
    return TextRegion(
        text=text, bbox=BBox(x0, y0, x1, y1), source=source, page=page
    )


class TestFallbackRescues:
    def test_far_below_caption_recovered(self):
        """Measured Fig 1.5 scene: caption 95 pt below, body block 141 pt above
        (inside the strict above-window → low margin → strict rejects)."""
        image = img(y0=521, y1=582, x0=342, x1=393)
        caption = region("Fig.1.5: a, b and c show the magnified schematic", 314, 677, 500, 710)
        filler = region("In the gaseous state, the particles move about randomly", 314, 368, 500, 380)

        result = match_image(image, [caption, filler], page_height=842.0)

        assert result.status is MatchStatus.MATCHED
        assert result.caption.startswith("Fig.1.5")
        assert result.method is MatchMethod.FALLBACK

    def test_above_caption_beats_below_name_label(self):
        """Measured Fig 12.8 case: true caption 138 pt above, decoy name below."""
        image = img(x0=58, y0=539, x1=137, y1=632)
        true_caption = region(
            "Fig. 12.8: Sound propagates as density or pressure variations", 56, 392, 277, 404
        )
        decoy = region("H. R. Hertz", 74, 633, 130, 643)

        result = match_image(image, [true_caption, decoy], page_height=842.0)

        assert result.status is MatchStatus.MATCHED
        assert result.caption.startswith("Fig. 12.8")

    def test_shared_caption_wins_for_second_image(self):
        """Measured Fig 1.10 case: caption reaches two figures; both map."""
        upper = img(index=1, x0=425, y0=373, x1=484, y1=444)
        lower = img(index=2, x0=419, y0=459, x1=471, y1=522)
        shared = region("Fig. 1.10: A model for happy converting of solid to liquid", 211, 541, 430, 577)
        noise = region("liquids and gases. For making this model you will need", 183, 141, 300, 200)

        for image in (upper, lower):
            result = match_image(image, [shared, noise], page_height=842.0)
            assert result.status is MatchStatus.MATCHED
            assert result.caption.startswith("Fig. 1.10")


class TestFallbackDiscipline:
    def test_zero_evidence_never_matches_even_in_fallback(self):
        """`H. R. Hertz` / `Megaphone` / `Exercises` stay unmatched."""
        image = img()
        for text in ("H. R. Hertz", "Megaphone", "Exercises", "Group Activity"):
            decoy = region(text, 110, 410, 230, 425)
            result = match_image(image, [decoy], page_height=842.0)
            assert result.status is MatchStatus.CAPTION_NOT_FOUND, text

    def test_mid_text_mention_never_matches(self):
        image = img()
        mention = region("shown in Fig. 12.8 above as density variations", 56, 424, 277, 436)
        result = match_image(image, [mention], page_height=842.0)
        assert result.status is MatchStatus.CAPTION_NOT_FOUND

    def test_neighboring_pages_never_searched(self):
        """§17: the fallback stays on the same page."""
        image = img(page=1)
        other_page_caption = region("Fig. 2.1: perfect caption", 110, 410, 290, 430, page=2)
        result = match_image(image, [other_page_caption], page_height=842.0)
        assert result.status is MatchStatus.CAPTION_NOT_FOUND

    def test_no_candidates_reports_not_found_with_zero_confidence(self):
        image = img()
        result = match_image(image, [], page_height=842.0)
        assert result.status is MatchStatus.CAPTION_NOT_FOUND
        assert result.caption is None
        assert result.confidence == 0.0
        assert result.method is MatchMethod.NO_RELIABLE_CANDIDATE


class TestSeriesPassthrough:
    def _figure(self, occurrence):
        return ExtractedFigure(occurrence=occurrence, png=b"", kind=FigureKind.COMPOSITE)

    def test_stacked_series_caption_assigned_to_upper_figure(self):
        """Measured Fig 1.6 case: caption under the bottom figure covers both."""
        upper = img(index=1, x0=326, y0=223, x1=439, y1=409)
        lower = img(index=2, x0=331, y0=475, x1=439, y1=639)
        results = {
            lower.image_id: MatchResult(
                image_id=lower.image_id,
                caption="Fig. 1.6: (a) Conversion of ice to water, (b) conversion of water to water vapour",
                confidence=0.62,
                status=MatchStatus.MATCHED,
                method=MatchMethod.NATIVE_TEXT,
            ),
            upper.image_id: MatchResult(
                image_id=upper.image_id,
                caption=None,
                confidence=0.4,
                status=MatchStatus.CAPTION_NOT_FOUND,
                method=MatchMethod.NO_RELIABLE_CANDIDATE,
            ),
        }
        assigned = series_passthrough([self._figure(upper), self._figure(lower)], results)
        assert assigned == 1
        upper_result = results[upper.image_id]
        assert upper_result.status is MatchStatus.MATCHED
        assert upper_result.caption.startswith("Fig. 1.6")
        assert upper_result.method is MatchMethod.FALLBACK
        assert upper_result.confidence == pytest.approx(0.62 * 0.85)

    def test_no_passthrough_without_series_marker(self):
        upper = img(index=1, y1=300)
        lower = img(index=2, y0=330, y1=500)
        results = {
            lower.image_id: MatchResult(
                image_id=lower.image_id, caption="Fig. 1.7: a standalone figure",
                confidence=0.8, status=MatchStatus.MATCHED, method=MatchMethod.NATIVE_TEXT,
            ),
            upper.image_id: MatchResult(
                image_id=upper.image_id, caption=None, confidence=0.1,
                status=MatchStatus.CAPTION_NOT_FOUND, method=MatchMethod.NO_RELIABLE_CANDIDATE,
            ),
        }
        assert series_passthrough([self._figure(upper), self._figure(lower)], results) == 0
        assert results[upper.image_id].status is MatchStatus.CAPTION_NOT_FOUND

    def test_no_passthrough_when_too_far(self):
        upper = img(index=1, y0=100, y1=300)
        lower = img(index=2, y0=500, y1=700)  # gap 200 > 80
        results = {
            lower.image_id: MatchResult(
                image_id=lower.image_id, caption="Fig. 1.6: (a) and (b) setups",
                confidence=0.8, status=MatchStatus.MATCHED, method=MatchMethod.NATIVE_TEXT,
            ),
        }
        assert series_passthrough([self._figure(upper), self._figure(lower)], results) == 0

    def test_no_passthrough_to_unmatched_winner(self):
        upper = img(index=1, y1=300)
        lower = img(index=2, y0=330, y1=500)
        results = {
            lower.image_id: MatchResult(
                image_id=lower.image_id, caption=None, confidence=0.0,
                status=MatchStatus.CAPTION_NOT_FOUND, method=MatchMethod.NO_RELIABLE_CANDIDATE,
            ),
        }
        assert series_passthrough([self._figure(upper), self._figure(lower)], results) == 0

    def test_figure_below_winner_never_gets_passthrough(self):
        """Only figures *above* a winner inherit: below ones match on their own."""
        winner = img(index=1, y0=100, y1=300)
        below = img(index=2, y0=330, y1=500)
        results = {
            winner.image_id: MatchResult(
                image_id=winner.image_id, caption="Fig. 1.6: (a) and (b)",
                confidence=0.8, status=MatchStatus.MATCHED, method=MatchMethod.NATIVE_TEXT,
            ),
            below.image_id: MatchResult(
                image_id=below.image_id, caption=None, confidence=0.2,
                status=MatchStatus.CAPTION_NOT_FOUND, method=MatchMethod.NO_RELIABLE_CANDIDATE,
            ),
        }
        assert series_passthrough([self._figure(winner), self._figure(below)], results) == 0


class TestFallbackConfigs:
    def test_fallback_weights_sum_to_one(self):
        total = (
            FALLBACK_SCORE_CONFIG.proximity
            + FALLBACK_SCORE_CONFIG.alignment
            + FALLBACK_SCORE_CONFIG.keyword
            + FALLBACK_SCORE_CONFIG.numbering
            + FALLBACK_SCORE_CONFIG.text_shape
            + FALLBACK_SCORE_CONFIG.layout
        )
        assert total == pytest.approx(1.0)

    def test_windows_broader_than_strict(self):
        from src.matching import CANDIDATE_CONFIG

        assert FALLBACK_CANDIDATE_CONFIG.max_below_gap_pt > CANDIDATE_CONFIG.max_below_gap_pt
        assert FALLBACK_CANDIDATE_CONFIG.max_above_gap_pt > CANDIDATE_CONFIG.max_above_gap_pt
