"""Comparison exports (PRD FR-30, FR-31): polarity, mirror and 500 ppi scaling.

All images are synthetic (tests/synthetic.py and closed-form patterns built here).
"""

from __future__ import annotations

import dataclasses
import math
from typing import cast

import cv2
import numpy as np
import pytest

from ridge import ExtractionResult, ParameterError, extract_fingerprint
from ridge.errors import ExportTooLargeError
from ridge.export import (
    ASSUMED_RIDGE_PERIOD_MM,
    MAX_EXPORT_PIXELS,
    RIDGE_PERIOD_UNCERTAINTY_PCT,
    ScaleEstimate,
    ScaleMethod,
    encode_png,
    make_comparison_export,
    mirror,
    scale_from_ridge_period,
    scale_from_ruler,
    to_comparison,
    to_ppi,
)
from tests.golden_cases import CASES_BY_NAME
from tests.synthetic import ImageU8

PX_PER_MM_AT_500PPI = 500.0 / 25.4
BAD_IMAGES: list[object] = [
    np.zeros((8, 8), np.float32),
    np.zeros((8, 8, 3), np.uint8),
    np.zeros((0, 8), np.uint8),
    np.zeros((8, 8), bool),
    [[0, 255]],
    None,
]
BAD_NUMBERS: list[object] = [0, -1.0, math.nan, math.inf, -math.inf, True, "500", None]


def pattern(height: int = 60, width: int = 80) -> ImageU8:
    """An asymmetric 0..255 test image, so flips and inversions are visible."""
    yy, xx = np.mgrid[0:height, 0:width]
    return cast(ImageU8, ((7 * xx + 3 * yy * yy) % 256).astype(np.uint8))


def stripes(height: int, width: int, period_px: int) -> ImageU8:
    """Vertical white ridges on black (like an extraction output), `period_px` apart."""
    xx = np.arange(width)
    row = np.where((xx % period_px) < period_px // 2, 255, 0).astype(np.uint8)
    return cast(ImageU8, np.repeat(row[None, :], height, axis=0))


def measured_period(image: ImageU8) -> float:
    """Ridge period along x from rising mean-crossings of the column profile (sub-pixel)."""
    profile = image.astype(np.float64).mean(axis=0)
    centred = profile - profile.mean()
    ups = np.flatnonzero((centred[:-1] < 0) & (centred[1:] >= 0))
    crossings = ups + (-centred[ups]) / (centred[ups + 1] - centred[ups])
    return float((crossings[-1] - crossings[0]) / (len(crossings) - 1))


def manual(px_per_mm: float, uncertainty_pct: float = 5.0) -> ScaleEstimate:
    return ScaleEstimate(px_per_mm=px_per_mm, method="manual", uncertainty_pct=uncertainty_pct)


@pytest.fixture(scope="module")
def whorl() -> ExtractionResult:
    """A real extraction of a synthetic whorl (ridges ~8.8 px apart, output_scale ~1.36)."""
    return extract_fingerprint(CASES_BY_NAME["whorl_default"].photo())


# ----------------------------------------------------------------------------- polarity and mirror


def test_to_comparison_inverts_exactly() -> None:
    image = pattern()
    before = image.copy()
    out = to_comparison(image)
    assert out.dtype == np.uint8
    assert np.array_equal(out.astype(np.int16), 255 - image.astype(np.int16))
    assert np.array_equal(to_comparison(out), image)
    assert np.array_equal(image, before)


def test_to_comparison_gives_dark_ridges_on_light() -> None:
    ridges = stripes(10, 20, 4)  # white ridges (255) on black (0)
    out = to_comparison(ridges)
    assert np.array_equal(out == 0, ridges == 255)
    assert np.array_equal(out == 255, ridges == 0)


def test_mirror_flips_left_to_right_exactly() -> None:
    image = pattern()
    before = image.copy()
    out = mirror(image)
    width = image.shape[1]
    for x in (0, 1, width // 2, width - 1):
        assert np.array_equal(out[:, x], image[:, width - 1 - x])
    assert np.array_equal(mirror(out), image)
    assert out.flags.c_contiguous
    out[0, 0] = 1  # a new array, not a view of the input
    assert np.array_equal(image, before)


@pytest.mark.parametrize("bad", BAD_IMAGES, ids=repr)
def test_transforms_reject_non_grayscale_u8(bad: object) -> None:
    with pytest.raises(ParameterError):
        to_comparison(cast(ImageU8, bad))
    with pytest.raises(ParameterError):
        mirror(cast(ImageU8, bad))
    with pytest.raises(ParameterError):
        to_ppi(cast(ImageU8, bad), photo_scale=manual(20.0), output_scale=1.0)
    with pytest.raises(ParameterError):
        encode_png(cast(ImageU8, bad), 500.0)


# ----------------------------------------------------------------------------- scale estimates


def test_scale_from_ruler_hand_computed() -> None:
    scale = scale_from_ruler((10.0, 20.0), (310.0, 420.0), 25.0)  # 300-400-500 triangle
    assert scale.method == "ruler"
    assert scale.px_per_mm == pytest.approx(500.0 / 25.0)
    assert scale.uncertainty_pct == pytest.approx(100.0 * 2 / 500.0)  # +-1 px on both points


def test_scale_from_ruler_accepts_lists_and_numpy_numbers() -> None:
    numpy_point = cast(tuple[float, float], (np.float32(0.0), np.int64(200)))
    scale = scale_from_ruler(cast(tuple[float, float], [0, 0]), numpy_point, np.float64(10.0))
    assert scale.px_per_mm == pytest.approx(20.0)
    assert type(scale.px_per_mm) is float


@pytest.mark.parametrize(
    ("p1", "p2", "distance_mm"),
    [
        ((5.0, 5.0), (5.0, 5.0), 10.0),  # same point
        ((0.0, 0.0), (100.0, 0.0), 0.0),
        ((0.0, 0.0), (100.0, 0.0), -10.0),
        ((0.0, 0.0), (100.0, 0.0), math.nan),
        ((0.0, 0.0), (100.0, 0.0), math.inf),
        ((math.nan, 0.0), (100.0, 0.0), 10.0),
        ((0.0, 0.0), (math.inf, 0.0), 10.0),
        ((0.0,), (100.0, 0.0), 10.0),
        ((0.0, 0.0, 0.0), (100.0, 0.0), 10.0),
        ("ab", (100.0, 0.0), 10.0),
        ((0.0, 0.0), (1e308, 1e308), 1e-300),  # px/mm overflows
    ],
)
def test_scale_from_ruler_rejects_bad_input(p1: object, p2: object, distance_mm: object) -> None:
    with pytest.raises(ParameterError):
        scale_from_ruler(cast(tuple[float, float], p1), cast(tuple[float, float], p2), cast(float, distance_mm))


def test_scale_from_ridge_period_hand_computed() -> None:
    scale = scale_from_ridge_period(9.4)
    assert scale.method == "ridge-period"
    assert scale.px_per_mm == pytest.approx(9.4 / 0.47)
    assert scale.uncertainty_pct == RIDGE_PERIOD_UNCERTAINTY_PCT == 15.0
    assert ASSUMED_RIDGE_PERIOD_MM == 0.47
    custom = scale_from_ridge_period(10.0, assumed_period_mm=0.5, uncertainty_pct=10.0)
    assert custom.px_per_mm == pytest.approx(20.0)
    assert custom.uncertainty_pct == 10.0


@pytest.mark.parametrize("bad", BAD_NUMBERS, ids=repr)
def test_scale_from_ridge_period_rejects_bad_numbers(bad: object) -> None:
    with pytest.raises(ParameterError):
        scale_from_ridge_period(cast(float, bad))
    with pytest.raises(ParameterError):
        scale_from_ridge_period(9.0, assumed_period_mm=cast(float, bad))


@pytest.mark.parametrize("bad", [-0.1, math.nan, math.inf, "5"], ids=repr)
def test_scale_uncertainty_must_be_finite_and_not_negative(bad: object) -> None:
    with pytest.raises(ParameterError):
        scale_from_ridge_period(9.0, uncertainty_pct=cast(float, bad))
    with pytest.raises(ParameterError):
        ScaleEstimate(px_per_mm=20.0, method="manual", uncertainty_pct=cast(float, bad))


def test_scale_estimate_validates_and_is_frozen() -> None:
    assert manual(20.0, 0.0).uncertainty_pct == 0.0
    with pytest.raises(ParameterError):
        ScaleEstimate(px_per_mm=0.0, method="manual", uncertainty_pct=1.0)
    with pytest.raises(ParameterError):
        ScaleEstimate(px_per_mm=20.0, method=cast(ScaleMethod, "guess"), uncertainty_pct=1.0)
    scale = manual(20.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        scale.px_per_mm = 1.0  # type: ignore[misc]  # assigning to a frozen field is the point of the test


# ----------------------------------------------------------------------------- 500 ppi scaling


@pytest.mark.parametrize(
    ("px_per_mm", "output_scale", "expected_side"),
    [
        (20.0, 1.0, 98),  # 100 * 19.685 / 20 = 98.4
        (10.0, 1.5, 131),  # 100 * 19.685 / 15 = 131.2
        (PX_PER_MM_AT_500PPI, 1.0, 100),
        (5.0, 2.0, 197),  # 100 * 19.685 / 10 = 196.9
    ],
)
def test_to_ppi_size_math(px_per_mm: float, output_scale: float, expected_side: int) -> None:
    image = pattern(100, 100)
    out, factor = to_ppi(image, photo_scale=manual(px_per_mm), output_scale=output_scale)
    assert factor == pytest.approx(PX_PER_MM_AT_500PPI / (px_per_mm * output_scale))
    assert out.dtype == np.uint8
    assert abs(out.shape[0] - expected_side) <= 1
    assert abs(out.shape[1] - expected_side) <= 1
    assert out.shape == (round(100 * factor), round(100 * factor))


def test_to_ppi_uses_area_when_shrinking_and_cubic_when_enlarging() -> None:
    image = stripes(50, 70, 6)
    for px_per_mm, interpolation in ((40.0, cv2.INTER_AREA), (8.0, cv2.INTER_CUBIC)):
        out, factor = to_ppi(image, photo_scale=manual(px_per_mm), output_scale=1.0)
        size = (round(70 * factor), round(50 * factor))
        expected = np.clip(np.rint(cv2.resize(image.astype(np.float32), size, interpolation=interpolation)), 0, 255)
        assert np.array_equal(out, expected.astype(np.uint8))


def test_to_ppi_anti_aliases_binary_input() -> None:
    out, _ = to_ppi(stripes(60, 90, 7), photo_scale=manual(30.0), output_scale=1.0)
    values = set(np.unique(out).tolist())
    assert {0, 255} <= values
    assert any(0 < v < 255 for v in values)


def test_to_ppi_target_resolution() -> None:
    out, factor = to_ppi(pattern(100, 100), photo_scale=manual(PX_PER_MM_AT_500PPI), output_scale=1.0, target_ppi=1000)
    assert factor == pytest.approx(2.0)
    assert out.shape == (200, 200)


def test_to_ppi_refuses_huge_exports() -> None:
    image = np.zeros((1000, 1000), np.uint8)
    with pytest.raises(ExportTooLargeError):  # 394 times larger: 1.5e11 px
        to_ppi(image, photo_scale=manual(0.05), output_scale=1.0)
    with pytest.raises(ExportTooLargeError):  # one side alone beyond the limit
        to_ppi(image, photo_scale=manual(1e-6), output_scale=1.0)
    with pytest.raises(ExportTooLargeError):  # the factor overflows to infinity
        to_ppi(image, photo_scale=manual(1e-300), output_scale=1e-10)
    assert MAX_EXPORT_PIXELS == 50_000_000


@pytest.mark.parametrize(
    ("px_per_mm", "output_scale"),
    [(1e-300, 1e-300), (1e300, 1e300), (1e6, 1.0)],  # underflow, overflow, shrinks to nothing
)
def test_to_ppi_rejects_unusable_scales(px_per_mm: float, output_scale: float) -> None:
    with pytest.raises(ParameterError):
        to_ppi(pattern(100, 100), photo_scale=manual(px_per_mm), output_scale=output_scale)


@pytest.mark.parametrize("bad", BAD_NUMBERS, ids=repr)
def test_to_ppi_rejects_bad_numbers(bad: object) -> None:
    with pytest.raises(ParameterError):
        to_ppi(pattern(), photo_scale=manual(20.0), output_scale=cast(float, bad))
    with pytest.raises(ParameterError):
        to_ppi(pattern(), photo_scale=manual(20.0), output_scale=1.0, target_ppi=cast(float, bad))


def test_to_ppi_rejects_bad_scale_and_resolution() -> None:
    with pytest.raises(ParameterError):
        to_ppi(pattern(), photo_scale=cast(ScaleEstimate, 20.0), output_scale=1.0)
    with pytest.raises(ParameterError):
        to_ppi(pattern(), photo_scale=manual(20.0), output_scale=1.0, target_ppi=200_000.0)


def test_ruler_calibrated_export_lands_within_two_percent() -> None:
    """FR-31: ridges 1 mm apart in a ruler-calibrated photo are 19.685 px apart at 500 ppi."""
    scale = scale_from_ruler((100.0, 50.0), (500.0, 50.0), 20.0)  # 400 px over 20 mm: 20 px/mm
    output_scale = 1.5  # the extraction output is 1.5 times finer than the photo
    ridges = stripes(300, 600, round(20 * output_scale))  # 1 mm period in output pixels
    result = ExtractionResult(image=ridges, period=20.0, found_finger=True, output_scale=output_scale)
    export = make_comparison_export(result, scale)
    assert measured_period(export.image) == pytest.approx(PX_PER_MM_AT_500PPI, rel=0.02)
    assert export.scale.uncertainty_pct == pytest.approx(0.5)


# ----------------------------------------------------------------------------- composition


def test_comparison_export_records_transforms() -> None:
    result = ExtractionResult(image=stripes(40, 60, 6), period=6.0, found_finger=True, output_scale=1.2)
    scale = scale_from_ruler((0.0, 0.0), (0.0, 400.0), 25.0)
    export = make_comparison_export(result, scale)
    assert export.transforms == ("polarity:dark-ridges", "mirror:horizontal", "scale:500ppi:ruler")
    assert export.ppi == 500.0
    assert export.scale is scale
    expected, factor = to_ppi(mirror(to_comparison(result.image)), photo_scale=scale, output_scale=1.2)
    assert export.factor == factor
    assert np.array_equal(export.image, expected)


def test_comparison_export_without_mirror_and_other_resolution() -> None:
    result = ExtractionResult(image=stripes(40, 60, 6), period=6.0, found_finger=True)
    export = make_comparison_export(result, manual(10.0), mirror_image=False, target_ppi=1000)
    assert export.transforms == ("polarity:dark-ridges", "scale:1000ppi:manual")
    assert export.ppi == 1000.0
    expected, _ = to_ppi(to_comparison(result.image), photo_scale=manual(10.0), output_scale=1.0, target_ppi=1000)
    assert np.array_equal(export.image, expected)
    fractional = make_comparison_export(result, manual(10.0), target_ppi=487.5)
    assert fractional.transforms[-1] == "scale:487.5ppi:manual"


def test_comparison_export_at_unit_factor_is_exact() -> None:
    """With a scale that needs no resampling, the export is exactly the inverted mirror image."""
    ridges = np.zeros((30, 50), np.uint8)
    ridges[:, :10] = 255  # a white ridge band on the left
    result = ExtractionResult(image=ridges, period=6.0, found_finger=True, output_scale=1.0)
    export = make_comparison_export(result, manual(PX_PER_MM_AT_500PPI))
    assert export.factor == pytest.approx(1.0)
    assert export.image.shape == ridges.shape
    assert np.all(export.image[:, -10:] == 0)  # dark ridge, now on the right
    assert np.all(export.image[:, :-10] == 255)


def test_export_of_a_real_extraction_with_ridge_period_scale(whorl: ExtractionResult) -> None:
    before = whorl.image.copy()
    export = make_comparison_export(whorl, scale_from_ridge_period(whorl.period))
    assert export.transforms == ("polarity:dark-ridges", "mirror:horizontal", "scale:500ppi:ridge-period")
    # By construction the export's ridge spacing is the assumed 0.47 mm at 500 ppi (9.25 px).
    spacing = whorl.period * whorl.output_scale * export.factor
    assert spacing == pytest.approx(ASSUMED_RIDGE_PERIOD_MM * PX_PER_MM_AT_500PPI, rel=1e-9)
    height, width = whorl.image.shape
    assert export.image.shape == (round(height * export.factor), round(width * export.factor))
    assert np.array_equal(whorl.image, before)
    assert np.mean(export.image) > 127  # mostly light background with dark ridges
