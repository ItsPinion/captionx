"""Tests for the BBox geometry primitive (plan.md §9)."""

import pytest

from src.models import BBox


class TestConstruction:
    def test_valid_box(self):
        b = BBox(10, 20, 110, 70)
        assert (b.x0, b.y0, x1 := b.x1, y1 := b.y1) == (10, 20, 110, 70)

    def test_degenerate_zero_size_allowed(self):
        b = BBox(5, 5, 5, 5)
        assert b.width == 0 and b.height == 0

    def test_inverted_x_rejected(self):
        with pytest.raises(ValueError):
            BBox(100, 10, 50, 60)

    def test_inverted_y_rejected(self):
        with pytest.raises(ValueError):
            BBox(10, 100, 50, 60)


class TestDimensions:
    def test_width_height_centers(self):
        b = BBox(10, 20, 110, 70)
        assert b.width == 100
        assert b.height == 50
        assert b.x_center == 60
        assert b.y_center == 45


class TestRelations:
    def test_intersection_full(self):
        a, b = BBox(0, 0, 100, 100), BBox(0, 0, 100, 100)
        assert a.intersection_area(b) == pytest.approx(10_000)

    def test_intersection_partial(self):
        a, b = BBox(0, 0, 100, 100), BBox(50, 50, 150, 150)
        assert a.intersection_area(b) == pytest.approx(2_500)

    def test_intersection_disjoint(self):
        a, b = BBox(0, 0, 10, 10), BBox(20, 20, 30, 30)
        assert a.intersection_area(b) == 0

    def test_horizontal_overlap_ratio(self):
        image = BBox(100, 0, 300, 50)  # width 200
        caption = BBox(150, 60, 250, 80)  # width 100, fully inside x-range
        # ratio is measured against the narrower box: full containment → 1.0
        assert caption.horizontal_overlap_ratio(image) == pytest.approx(1.0)
        assert image.horizontal_overlap_ratio(caption) == pytest.approx(1.0)
        # same width, 3/4 overlapping → 0.75
        wide = BBox(150, 60, 350, 80)
        assert image.horizontal_overlap_ratio(wide) == pytest.approx(0.75)

    def test_horizontal_overlap_disjoint_columns(self):
        left = BBox(0, 0, 100, 50)
        right = BBox(200, 0, 300, 50)
        assert left.horizontal_overlap_ratio(right) == 0

    def test_vertical_gap(self):
        image = BBox(100, 100, 300, 400)
        caption_below = BBox(120, 410, 280, 440)
        caption_above = BBox(120, 50, 280, 90)
        assert image.vertical_gap(caption_below) == pytest.approx(10)
        assert image.vertical_gap(caption_above) == pytest.approx(10)
        assert image.vertical_gap(BBox(120, 200, 280, 300)) == 0  # overlapping

    def test_is_below_is_above(self):
        image = BBox(100, 100, 300, 400)
        below = BBox(120, 410, 280, 440)
        above = BBox(120, 50, 280, 90)
        assert below.is_below(image)
        assert not below.is_above(image)
        assert above.is_above(image)
        assert not image.is_below(image)


class TestTransformsAndSerialization:
    def test_scaled_converts_pixel_to_points(self):
        # A box detected on a 2x render, converted back to PDF points.
        pixel_box = BBox(200, 400, 600, 900)
        points = pixel_box.scaled(1 / 2.0)
        assert points.to_list() == [100, 200, 300, 450]

    def test_to_list_from_list_roundtrip(self):
        b = BBox(1.5, 2.25, 3.0, 4.75)
        assert BBox.from_list(b.to_list()) == b
