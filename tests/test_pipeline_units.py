"""Unit tests for the pure pipeline helpers."""

from __future__ import annotations

import math
from typing import cast

import numpy as np
import pytest

from ridge.arrays import FloatImage
from ridge.pipeline.gabor import N_ORIENT, gabor_bank, oriented_filter, ridge_orientation
from ridge.pipeline.imgutil import disk, fill_holes, largest_component, masked_blur, remove_specks
from ridge.pipeline.mask import finger_mask
from ridge.pipeline.period import estimate_period
from tests.synthetic import finger_photo


def concentric(size: int, period: float) -> FloatImage:
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    r = np.hypot(xx - size / 2, yy - size / 2)
    return cast(FloatImage, (0.5 + 0.5 * np.cos(2 * np.pi * r / period)).astype(np.float32))


@pytest.mark.parametrize("diameter", [0, 2.4, 3, 8, 13.6])
def test_disk_is_odd_and_at_least_three(diameter: float) -> None:
    d = disk(diameter).shape[0]
    assert d % 2 == 1
    assert d >= 3


def test_largest_component_keeps_biggest_blob() -> None:
    mask = np.zeros((20, 20), bool)
    mask[1:4, 1:4] = True
    mask[10:18, 10:18] = True
    kept = largest_component(mask)
    assert kept[12, 12]
    assert not kept[2, 2]


def test_largest_component_of_empty_mask_is_empty() -> None:
    assert not largest_component(np.zeros((5, 5), bool)).any()


def test_fill_holes_fills_enclosed_area_only() -> None:
    ring = np.zeros((11, 11), bool)
    ring[2:9, 2:9] = True
    ring[4:7, 4:7] = False
    filled = fill_holes(ring)
    assert filled[5, 5]
    assert not filled[0, 0]


def test_remove_specks_drops_small_components() -> None:
    binary = np.zeros((20, 20), bool)
    binary[0, 0] = True
    binary[5:15, 5:15] = True
    cleaned = remove_specks(binary, min_area=4)
    assert not cleaned[0, 0]
    assert cleaned[10, 10]


def test_masked_blur_has_no_halo_outside_mask() -> None:
    img = np.zeros((40, 40), np.float32)
    mask = np.zeros((40, 40), np.float32)
    img[:, :20] = 1.0
    mask[:, :20] = 1.0
    blurred = masked_blur(img, mask, 3.0)
    assert np.allclose(blurred[:, :18], 1.0, atol=1e-4)  # no darkening from the zeros outside


@pytest.mark.parametrize("period", [6.0, 9.0, 14.0])
def test_estimate_period_on_uniform_ridges(period: float) -> None:
    gray = concentric(600, period)
    mask = np.ones(gray.shape, bool)
    assert estimate_period(gray, mask) == pytest.approx(period, rel=0.05)  # PRD FR-3


def test_gabor_bank_kernels_have_zero_dc_and_unit_gain() -> None:
    period = 12.0
    kernels, bank_power = gabor_bank(period)
    assert len(kernels) == N_ORIENT
    half = kernels[0].shape[0] // 2
    x = np.arange(-half, half + 1, dtype=np.float64)[None, :].repeat(2 * half + 1, axis=0)
    wave = np.cos(2 * math.pi * x / period)
    assert abs(float(kernels[0].sum())) < 1e-4
    assert float((kernels[0] * wave).sum()) == pytest.approx(1.0, rel=1e-3)
    assert bank_power >= 1.0


def test_ridge_orientation_across_vertical_ridges_is_horizontal() -> None:
    xx = np.mgrid[0:64, 0:64][1].astype(np.float32)
    img = np.cos(2 * np.pi * xx / 12.0).astype(np.float32)
    phi = ridge_orientation(img, np.ones_like(img), 12.0)
    centre = phi[16:48, 16:48]
    assert float(np.median(np.minimum(centre, math.pi - centre))) < 0.05  # ~0 rad (or ~pi)


def test_oriented_filter_passes_matching_ridges() -> None:
    xx = np.mgrid[0:64, 0:64][1].astype(np.float32)
    img = np.cos(2 * np.pi * xx / 12.0).astype(np.float32)
    kernels, _ = gabor_bank(12.0)
    out, power = oriented_filter(img, np.zeros_like(img), kernels)
    assert float(np.corrcoef(out[16:48, 16:48].ravel(), img[16:48, 16:48].ravel())[0, 1]) > 0.99
    assert float(power.min()) >= 0.0


def test_finger_mask_none_without_skin_colour() -> None:
    grey = finger_photo(concentric(300, 9.0), colour=False)
    assert finger_mask(grey) is None


def test_finger_mask_finds_skin() -> None:
    photo = finger_photo(concentric(300, 9.0))
    mask = finger_mask(photo)
    assert mask is not None
    assert mask[150, 150]
    assert not mask[2, 2]
