"""Tests for CaptionCandidate and MatchResult (plan.md §9 / §13)."""

import pytest

from src.models import (
    BBox,
    CaptionCandidate,
    ImageOccurrence,
    MatchMethod,
    MatchResult,
    MatchStatus,
    TextSource,
)


class TestCaptionCandidate:
    def test_defaults(self):
        c = CaptionCandidate(
            text="Fig. 3.1: Structure of the cell",
            bbox=BBox(100, 410, 300, 430),
            source=TextSource.NATIVE_PDF,
            image_id="page_003_image_01",
        )
        assert c.features == {}
        assert c.score == 0.0

    def test_feature_dicts_not_shared_between_instances(self):
        a = CaptionCandidate(
            text="a", bbox=BBox(0, 0, 1, 1), source="ocr", image_id="i1"
        )
        b = CaptionCandidate(
            text="b", bbox=BBox(0, 0, 1, 1), source="ocr", image_id="i2"
        )
        a.features["proximity"] = 0.5
        assert b.features == {}

    def test_roundtrip_preserves_features(self):
        c = CaptionCandidate(
            text="Fig. 3.1",
            bbox=BBox(1, 2, 3, 4),
            source=TextSource.OCR,
            image_id="page_001_image_01",
            features={"proximity": 0.9, "keyword": 1.0},
            score=0.83,
        )
        assert CaptionCandidate.from_dict(c.to_dict()) == c


class TestMatchResult:
    def test_valid_match(self):
        m = MatchResult(
            image_id="page_003_image_01",
            caption="Fig. 3.1: Structure of the cell",
            confidence=0.94,
            status=MatchStatus.MATCHED,
            method=MatchMethod.NATIVE_TEXT,
        )
        assert 0.0 <= m.confidence <= 1.0

    def test_confidence_clamped_high(self):
        m = MatchResult(
            image_id="i", caption="c", confidence=1.5,
            status="matched", method="native_text",
        )
        assert m.confidence == 1.0

    def test_confidence_clamped_low(self):
        m = MatchResult(
            image_id="i", caption=None, confidence=-0.2,
            status="caption_not_found", method="no_reliable_candidate",
        )
        assert m.confidence == 0.0

    def test_matched_without_caption_rejected(self):
        with pytest.raises(ValueError):
            MatchResult(
                image_id="i", caption=None, confidence=0.9,
                status="matched", method="native_text",
            )

    def test_caption_not_found_with_caption_rejected(self):
        with pytest.raises(ValueError):
            MatchResult(
                image_id="i", caption="invented", confidence=0.2,
                status="caption_not_found", method="no_reliable_candidate",
            )

    def test_as_result_entry_matches_plan_schema(self):
        """plan.md §13 required fields: image/page/caption/confidence/status/method."""
        image = ImageOccurrence(
            page=3, index=1, width=640, height=480,
            filename="biology_ch01_page_03_image_01.png",
        )
        m = MatchResult(
            image_id=image.image_id,
            caption="Fig. 3.1: Structure of the cell",
            confidence=0.94,
            status=MatchStatus.MATCHED,
            method=MatchMethod.NATIVE_TEXT,
        )
        entry = m.as_result_entry(image)
        assert entry == {
            "image": "biology_ch01_page_03_image_01.png",
            "page": 3,
            "caption": "Fig. 3.1: Structure of the cell",
            "confidence": 0.94,
            "status": "matched",
            "method": "native_text",
        }

    def test_as_result_entry_caption_not_found_example(self):
        """plan.md §13 `caption_not_found` example."""
        image = ImageOccurrence(
            page=8, index=2, width=100, height=100,
            filename="biology_ch01_page_08_image_02.png",
        )
        m = MatchResult(
            image_id=image.image_id,
            caption=None,
            confidence=0.18,
            status=MatchStatus.CAPTION_NOT_FOUND,
            method=MatchMethod.NO_RELIABLE_CANDIDATE,
        )
        entry = m.as_result_entry(image)
        assert entry["caption"] is None
        assert entry["status"] == "caption_not_found"
        assert entry["method"] == "no_reliable_candidate"

    def test_roundtrip(self):
        m = MatchResult(
            image_id="page_002_image_01",
            caption="Figure 4.1",
            confidence=0.71,
            status="matched",
            method="fallback",
        )
        assert MatchResult.from_dict(m.to_dict()) == m


class TestContractStrings:
    """Enum values must equal the JSON strings shared with the TypeScript side."""

    @pytest.mark.parametrize(
        "enum_cls,expected",
        [
            (MatchStatus, ["matched", "caption_not_found"]),
            (MatchMethod, ["native_text", "ocr", "fallback", "no_reliable_candidate"]),
            (TextSource, ["native_pdf", "ocr"]),
        ],
    )
    def test_values(self, enum_cls, expected):
        assert [e.value for e in enum_cls] == expected

    def test_document_source_values(self):
        from src.models import DocumentSource

        assert sorted(e.value for e in DocumentSource) == ["upload", "url"]
